import json
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import Mock

import pytest
from django.db import connection, connections
from jsonschema import Draft202012Validator, FormatChecker
from rest_framework.response import Response
from rest_framework.test import APIClient

from outbox.models import OutboxEvent
from purchases import services
from purchases.clients import PaymentOutcome, PaymentResult
from purchases.models import Purchase
from ticket_types.models import TicketType
from tickets.models import Ticket, TicketStateChange

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

PURCHASES = "/api/ticketing/v1/purchases"
CORRELATION_ID = "ticketing-test-correlation"
EVENT_SCHEMA = Path(__file__).resolve().parents[4] / "contracts/events/ticket-purchased.v1.schema.json"


def buy(
    client: APIClient,
    ticket_type: TicketType,
    key: str | None,
    *,
    price: int | None = None,
    token: str = "sim_approve",
) -> Response:
    headers = {"HTTP_X_CORRELATION_ID": CORRELATION_ID}
    if key is not None:
        headers["HTTP_IDEMPOTENCY_KEY"] = key
    return client.post(
        PURCHASES,
        {
            "ticketTypeId": str(ticket_type.id),
            "expectedPriceCents": ticket_type.price_cents if price is None else price,
            "paymentMethodToken": token,
        },
        format="json",
        **headers,
    )


@pytest.mark.req("FR-032")
@pytest.mark.req("FR-033")
@pytest.mark.req("FR-035")
@pytest.mark.req("NFR-006")
@pytest.mark.contract
def test_approved_purchase_issues_ticket_and_stores_event(
    passenger: APIClient, ticket_type: TicketType, payment: Mock
) -> None:
    response = buy(passenger, ticket_type, str(uuid.uuid4()))

    assert response.status_code == 201
    assert response["X-Correlation-Id"] == CORRELATION_ID
    purchase = Purchase.objects.get()
    ticket = Ticket.objects.get(purchase=purchase)
    assert response.json()["id"] == str(purchase.id)
    assert response.json()["ticketId"] == str(ticket.id)
    assert purchase.status == Purchase.Status.COMPLETED
    assert ticket.terms_snapshot == ticket_type.terms
    assert (ticket.price_cents, ticket.currency) == (ticket_type.price_cents, ticket_type.currency)
    payment.pay.assert_called_once_with(
        idempotency_key=purchase.id,
        amount_cents=ticket_type.price_cents,
        currency=ticket_type.currency,
        payment_method_token="sim_approve",
    )
    state_change = TicketStateChange.objects.get()
    assert (state_change.ticket_id, state_change.from_status, state_change.to_status, state_change.reason) == (
        ticket.id,
        None,
        Ticket.Status.ISSUED,
        TicketStateChange.Reason.PURCHASE,
    )
    event = OutboxEvent.objects.get()
    assert event.routing_key == "ticketing.ticket.purchased"
    assert event.status == OutboxEvent.Status.PENDING
    Draft202012Validator(
        json.loads(EVENT_SCHEMA.read_text(encoding="utf-8")),
        format_checker=FormatChecker(),
    ).validate(event.body)
    assert event.body["eventId"] == str(event.event_id)
    assert event.body["correlationId"] == CORRELATION_ID
    assert event.body["payload"] == {
        "purchaseId": str(purchase.id),
        "ticketId": str(ticket.id),
        "passengerId": str(purchase.passenger_id),
        "ticketTypeId": str(ticket_type.id),
        "priceCents": ticket_type.price_cents,
        "currency": ticket_type.currency,
        "issuedAt": event.body["occurredAt"],
    }
    assert "paymentMethodToken" not in response.json()


@pytest.mark.req("FR-033")
@pytest.mark.req("NFR-013")
def test_completion_replays_after_retirement_and_rejects_changed_payload(
    passenger: APIClient, ticket_type: TicketType, payment: Mock
) -> None:
    key = str(uuid.uuid4())
    first = buy(passenger, ticket_type, key)
    assert first.status_code == 201
    ticket_type.status = TicketType.Status.RETIRED
    ticket_type.save(update_fields=["status"])

    replay = buy(passenger, ticket_type, key)
    conflict = buy(passenger, ticket_type, key, token="sim_decline")

    assert replay.status_code == 201
    assert replay.json() == first.json()
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    payment.pay.assert_called_once()
    assert Purchase.objects.count() == Ticket.objects.count() == 1
    assert TicketStateChange.objects.count() == OutboxEvent.objects.count() == 1


@pytest.mark.skipif(connection.vendor == "sqlite", reason="Concurrent test requires PostgreSQL row locking")
@pytest.mark.req("FR-033")
@pytest.mark.req("NFR-013")
@pytest.mark.django_db(transaction=True)
def test_concurrent_purchase_retries_create_one_purchase_and_ticket(
    api_client_for: Callable[[uuid.UUID, str], APIClient], ticket_type: TicketType, payment: Mock
) -> None:
    passenger_id = uuid.uuid4()
    key = str(uuid.uuid4())
    worker_count = 10
    start = Barrier(worker_count)

    def submit() -> tuple[int, str]:
        try:
            client = api_client_for(passenger_id, "passenger")
            start.wait(timeout=15)
            response = buy(client, ticket_type, key)
            return response.status_code, response.json()["id"]
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = list(executor.map(lambda _: submit(), range(worker_count)))

    purchase = Purchase.objects.get()
    assert purchase.status == Purchase.Status.COMPLETED
    assert {status for status, _ in results} <= {201, 202}
    assert any(status == 201 for status, _ in results)
    assert {purchase_id for _, purchase_id in results} == {str(purchase.id)}
    payment.pay.assert_called_once()
    assert Ticket.objects.count() == TicketStateChange.objects.count() == OutboxEvent.objects.count() == 1


@pytest.mark.req("FR-036")
@pytest.mark.req("FR-081")
@pytest.mark.req("NFR-013")
def test_pending_purchase_preserves_terms_when_approved_later(
    passenger: APIClient, ticket_type: TicketType, payment: Mock
) -> None:
    payment.pay.return_value = PaymentResult(PaymentOutcome.UNCERTAIN)
    key = str(uuid.uuid4())
    pending = buy(passenger, ticket_type, key)
    purchase = Purchase.objects.get()

    assert pending.status_code == 202
    assert pending.json()["status"] == Purchase.Status.PENDING
    assert pending["Location"] == f"{PURCHASES}/{purchase.id}"
    assert int(pending["Retry-After"]) > 0
    assert passenger.get(pending["Location"]).json()["status"] == Purchase.Status.PENDING
    assert buy(passenger, ticket_type, key).status_code == 202
    payment.pay.assert_called_once()
    assert not Ticket.objects.exists()
    assert not OutboxEvent.objects.exists()

    original_terms = ticket_type.terms
    original_price = ticket_type.price_cents
    ticket_type.terms = {"journeys": 5}
    ticket_type.price_cents = 250
    ticket_type.status = TicketType.Status.RETIRED
    ticket_type.save(update_fields=["terms", "price_cents", "status"])

    payment_id = str(uuid.uuid4())
    services.finalize_approved(purchase.id, payment_id=payment_id)
    services.finalize_approved(purchase.id, payment_id=payment_id)

    completed = passenger.get(pending["Location"])
    ticket = Ticket.objects.get()
    assert completed.status_code == 200
    assert completed.json()["status"] == Purchase.Status.COMPLETED
    assert completed.json()["ticketId"] == str(ticket.id)
    assert ticket.terms_snapshot == original_terms
    assert ticket.price_cents == original_price
    assert TicketStateChange.objects.count() == OutboxEvent.objects.count() == 1


@pytest.mark.req("FR-033")
@pytest.mark.req("NFR-022")
@pytest.mark.failure
def test_failed_outbox_insert_rolls_back_issuance_and_can_be_retried(
    passenger: APIClient, ticket_type: TicketType, payment: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    payment.pay.return_value = PaymentResult(PaymentOutcome.UNCERTAIN)
    assert buy(passenger, ticket_type, str(uuid.uuid4())).status_code == 202
    purchase = Purchase.objects.get()
    payment_id = str(uuid.uuid4())

    with monkeypatch.context() as patch:
        patch.setattr(services, "enqueue", Mock(side_effect=RuntimeError("outbox write failed")))
        with pytest.raises(RuntimeError, match="outbox write failed"):
            services.finalize_approved(purchase.id, payment_id=payment_id)

    purchase.refresh_from_db()
    assert purchase.status == Purchase.Status.PENDING
    assert not Ticket.objects.exists()
    assert not TicketStateChange.objects.exists()
    assert not OutboxEvent.objects.exists()

    assert services.finalize_approved(purchase.id, payment_id=payment_id).status == Purchase.Status.COMPLETED
    assert Ticket.objects.count() == TicketStateChange.objects.count() == OutboxEvent.objects.count() == 1


@pytest.mark.req("FR-032")
@pytest.mark.req("FR-037")
def test_payment_decline_is_replayed_without_issuing_a_ticket(
    passenger: APIClient, ticket_type: TicketType, payment: Mock
) -> None:
    payment.pay.return_value = PaymentResult(PaymentOutcome.DECLINED)
    key = str(uuid.uuid4())

    first = buy(passenger, ticket_type, key, token="sim_decline")
    replay = buy(passenger, ticket_type, key, token="sim_decline")

    assert first.status_code == replay.status_code == 422
    assert first.json() == replay.json()
    assert first.json()["error"]["code"] == "PAYMENT_DECLINED"
    assert Purchase.objects.get().status == Purchase.Status.FAILED
    assert not Ticket.objects.exists()
    assert not OutboxEvent.objects.exists()
    payment.pay.assert_called_once()


@pytest.mark.req("FR-032")
@pytest.mark.parametrize(
    ("condition", "http_status", "code"),
    [
        ("missing_type", 404, "TICKET_TYPE_NOT_FOUND"),
        ("retired", 422, "TICKET_TYPE_NOT_AVAILABLE"),
        ("price_changed", 422, "PRICE_CHANGED"),
    ],
)
def test_purchase_rejects_unavailable_terms_before_contacting_payment(
    passenger: APIClient, ticket_type: TicketType, payment: Mock, condition: str, http_status: int, code: str
) -> None:
    if condition == "missing_type":
        ticket_type.id = uuid.uuid4()
    if condition == "retired":
        ticket_type.status = TicketType.Status.RETIRED
        ticket_type.save(update_fields=["status"])
    price = ticket_type.price_cents + 1 if condition == "price_changed" else ticket_type.price_cents

    response = buy(passenger, ticket_type, str(uuid.uuid4()), price=price)

    assert response.status_code == http_status
    assert response.json()["error"]["code"] == code
    payment.pay.assert_not_called()
    assert not Purchase.objects.exists()


@pytest.mark.req("NFR-013")
@pytest.mark.parametrize("key", [None, "not-a-uuid"])
def test_purchase_requires_uuid_idempotency_key(
    passenger: APIClient, ticket_type: TicketType, payment: Mock, key: str | None
) -> None:
    response = buy(passenger, ticket_type, key)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    assert response.json()["error"]["correlationId"] == CORRELATION_ID
    payment.pay.assert_not_called()
    assert not Purchase.objects.exists()


@pytest.mark.req("FR-102")
def test_purchase_private_to_passenger_and_key_scoped_per_passenger(
    api_client_for: Callable[[uuid.UUID, str], APIClient], ticket_type: TicketType, payment: Mock
) -> None:
    first = api_client_for(uuid.uuid4(), "passenger")
    second = api_client_for(uuid.uuid4(), "passenger")
    staff = api_client_for(uuid.uuid4(), "staff")
    key = str(uuid.uuid4())

    assert buy(APIClient(), ticket_type, key).status_code == 401
    assert buy(staff, ticket_type, key).status_code == 403
    payment.pay.assert_not_called()

    owned = buy(first, ticket_type, key)
    assert owned.status_code == 201
    path = f"{PURCHASES}/{owned.json()['id']}"
    assert first.get(path).status_code == 200
    assert second.get(path).status_code == 404
    own_purchase = buy(second, ticket_type, key)
    assert own_purchase.status_code == 201
    assert own_purchase.json()["id"] != owned.json()["id"]
    assert payment.pay.call_count == 2
