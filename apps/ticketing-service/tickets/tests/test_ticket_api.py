import uuid
from datetime import UTC, datetime, timedelta

import pytest
from rest_framework.test import APIClient

from purchases.models import Purchase
from ticket_types.models import TicketType
from tickets.models import Ticket, TicketStateChange, ValidationAttempt, Validator

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

TICKETS_URL = "/api/ticketing/v1/tickets"


def _create_ticket(
    passenger_id: uuid.UUID,
    ticket_type: TicketType,
    *,
    status: str = Ticket.Status.ISSUED,
    remaining_journeys: int | None = None,
    activated_at: datetime | None = None,
    valid_until: datetime | None = None,
    issued_at: datetime | None = None,
) -> Ticket:
    now = issued_at or datetime.now(UTC)
    purchase = Purchase.objects.create(
        passenger_id=passenger_id,
        idempotency_key=uuid.uuid4(),
        request_fingerprint="test-fingerprint",
        ticket_type=ticket_type,
        terms_snapshot=ticket_type.terms,
        price_cents=ticket_type.price_cents,
        currency=ticket_type.currency,
        payment_method_token="tok_test",
        status=Purchase.Status.COMPLETED,
        payment_id=f"pay_{uuid.uuid4()}",
        next_attempt_at=now,
        completed_at=now,
        response_status=201,
        response_body={},
        correlation_id="test-corr",
    )
    return Ticket.objects.create(
        purchase=purchase,
        passenger_id=passenger_id,
        ticket_type=ticket_type,
        terms_snapshot=purchase.terms_snapshot,
        price_cents=purchase.price_cents,
        currency=purchase.currency,
        status=status,
        issued_at=now,
        remaining_journeys=remaining_journeys,
        activated_at=activated_at,
        valid_until=valid_until,
    )


@pytest.mark.req("FR-034")
def test_list_tickets_empty(passenger: APIClient) -> None:
    response = passenger.get(TICKETS_URL)
    assert response.status_code == 200
    data = response.json()
    assert data["results"] == []


@pytest.mark.req("FR-034")
def test_list_passenger_tickets_with_type_state_and_remaining_journeys(
    passenger: APIClient, passenger_id: uuid.UUID, ticket_type: TicketType
) -> None:
    ticket = _create_ticket(passenger_id, ticket_type)

    response = passenger.get(TICKETS_URL)
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 1

    item = data["results"][0]
    assert item["id"] == str(ticket.id)
    assert item["status"] == "ISSUED"
    assert item["ticketType"]["code"] == ticket_type.code
    assert item["ticketType"]["name"] == ticket_type.name
    assert item["remainingJourneys"] == 10
    assert item["terms"] == {"journeys": 10}
    assert item["priceCents"] == ticket_type.price_cents
    assert item["currency"] == "EUR"
    assert item["validationHistory"] == []


@pytest.mark.req("FR-034")
@pytest.mark.req("FR-102")
def test_list_tickets_excludes_other_passengers(
    passenger: APIClient,
    passenger_id: uuid.UUID,
    other_passenger: APIClient,
    other_passenger_id: uuid.UUID,
    ticket_type: TicketType,
) -> None:
    ticket_a = _create_ticket(passenger_id, ticket_type)
    ticket_b = _create_ticket(other_passenger_id, ticket_type)

    res_a = passenger.get(TICKETS_URL)
    assert res_a.status_code == 200
    ids_a = [t["id"] for t in res_a.json()["results"]]
    assert ids_a == [str(ticket_a.id)]

    res_b = other_passenger.get(TICKETS_URL)
    assert res_b.status_code == 200
    ids_b = [t["id"] for t in res_b.json()["results"]]
    assert ids_b == [str(ticket_b.id)]


@pytest.mark.req("FR-034")
def test_get_ticket_detail_with_validation_history_ordered_newest_first(
    passenger: APIClient, passenger_id: uuid.UUID, ticket_type: TicketType
) -> None:
    ticket = _create_ticket(passenger_id, ticket_type)
    stop_1 = uuid.uuid4()
    stop_2 = uuid.uuid4()
    validator = Validator.objects.create(stop_id=stop_1, code="VAL-01")

    now = datetime.now(UTC)
    v1 = ValidationAttempt.objects.create(
        ticket=ticket,
        validator=validator,
        stop_id=stop_1,
        result=ValidationAttempt.Result.ACCEPTED,
        decided_at=now - timedelta(minutes=10),
    )
    v2 = ValidationAttempt.objects.create(
        ticket=ticket,
        validator=validator,
        stop_id=stop_2,
        result=ValidationAttempt.Result.REJECTED,
        reason=ValidationAttempt.Reason.NO_JOURNEYS_LEFT,
        decided_at=now - timedelta(minutes=2),
    )

    response = passenger.get(f"{TICKETS_URL}/{ticket.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(ticket.id)
    assert len(data["validationHistory"]) == 2

    # Newest first: v2 then v1
    assert data["validationHistory"][0]["id"] == str(v2.id)
    assert data["validationHistory"][0]["result"] == "REJECTED"
    assert data["validationHistory"][0]["reason"] == "NO_JOURNEYS_LEFT"
    assert data["validationHistory"][0]["stopId"] == str(stop_2)

    assert data["validationHistory"][1]["id"] == str(v1.id)
    assert data["validationHistory"][1]["result"] == "ACCEPTED"
    assert data["validationHistory"][1]["reason"] is None
    assert data["validationHistory"][1]["stopId"] == str(stop_1)


@pytest.mark.req("FR-034")
@pytest.mark.req("FR-102")
def test_get_ticket_detail_for_other_passenger_returns_404(
    passenger: APIClient, other_passenger_id: uuid.UUID, ticket_type: TicketType
) -> None:
    ticket_other = _create_ticket(other_passenger_id, ticket_type)

    response = passenger.get(f"{TICKETS_URL}/{ticket_other.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "TICKET_NOT_FOUND"


@pytest.mark.req("FR-034")
def test_get_unknown_ticket_returns_404(passenger: APIClient) -> None:
    response = passenger.get(f"{TICKETS_URL}/{uuid.uuid4()}")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "TICKET_NOT_FOUND"


@pytest.mark.req("FR-034")
def test_reconcile_ticket_list_after_validation(
    passenger: APIClient, passenger_id: uuid.UUID, ticket_type: TicketType
) -> None:
    """After a successful validation, reload the account ticket list and reconcile its

    displayed remaining entitlement and history with the persisted result (AC-3).
    """
    ticket = _create_ticket(passenger_id, ticket_type)

    # Before validation: 10 journeys, ISSUED, empty history
    res_before = passenger.get(TICKETS_URL)
    assert res_before.status_code == 200
    ticket_before = res_before.json()["results"][0]
    assert ticket_before["status"] == "ISSUED"
    assert ticket_before["remainingJourneys"] == 10
    assert len(ticket_before["validationHistory"]) == 0

    # Simulate validation occurring:
    validation_time = datetime.now(UTC)
    stop_id = uuid.uuid4()
    validator = Validator.objects.create(stop_id=stop_id, code="VAL-STOP-A")

    ticket.status = Ticket.Status.ACTIVE
    ticket.remaining_journeys = 9
    ticket.activated_at = validation_time
    ticket.save()

    TicketStateChange.objects.create(
        ticket=ticket,
        from_status=Ticket.Status.ISSUED,
        to_status=Ticket.Status.ACTIVE,
        reason=TicketStateChange.Reason.VALIDATION,
        correlation_id="val-corr-1",
    )
    val_attempt = ValidationAttempt.objects.create(
        ticket=ticket,
        validator=validator,
        stop_id=stop_id,
        result=ValidationAttempt.Result.ACCEPTED,
        decided_at=validation_time,
    )

    # Reload account ticket list
    res_after = passenger.get(TICKETS_URL)
    assert res_after.status_code == 200
    ticket_after = res_after.json()["results"][0]

    # Reconciled remaining entitlement and history
    assert ticket_after["status"] == "ACTIVE"
    assert ticket_after["remainingJourneys"] == 9
    assert ticket_after["activatedAt"] is not None
    assert len(ticket_after["validationHistory"]) == 1
    assert ticket_after["validationHistory"][0]["id"] == str(val_attempt.id)
    assert ticket_after["validationHistory"][0]["result"] == "ACCEPTED"
    assert ticket_after["validationHistory"][0]["stopId"] == str(stop_id)


@pytest.mark.req("FR-034")
def test_period_pass_validity_dates(
    passenger: APIClient, passenger_id: uuid.UUID, period_ticket_type: TicketType
) -> None:
    now = datetime.now(UTC)
    valid_until = now + timedelta(hours=24)
    ticket = _create_ticket(
        passenger_id,
        period_ticket_type,
        status=Ticket.Status.ACTIVE,
        remaining_journeys=None,
        activated_at=now,
        valid_until=valid_until,
    )

    response = passenger.get(f"{TICKETS_URL}/{ticket.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["remainingJourneys"] is None
    assert data["activatedAt"] is not None
    assert data["validUntil"] is not None


@pytest.mark.req("FR-034")
def test_unauthenticated_request_rejected() -> None:
    anonymous = APIClient()
    response = anonymous.get(TICKETS_URL)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.req("FR-034")
def test_non_passenger_role_forbidden(api_client_for: pytest.FixtureRequest, passenger_id: uuid.UUID) -> None:
    staff_client = api_client_for(passenger_id, "staff")
    response = staff_client.get(TICKETS_URL)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.req("FR-034")
def test_ticket_list_cursor_pagination(passenger: APIClient, passenger_id: uuid.UUID, ticket_type: TicketType) -> None:
    base_time = datetime.now(UTC)
    t1 = _create_ticket(passenger_id, ticket_type, issued_at=base_time - timedelta(minutes=10))
    t2 = _create_ticket(passenger_id, ticket_type, issued_at=base_time - timedelta(minutes=5))
    t3 = _create_ticket(passenger_id, ticket_type, issued_at=base_time)

    # Page 1: limit 2
    res_page1 = passenger.get(f"{TICKETS_URL}?limit=2")
    assert res_page1.status_code == 200
    data1 = res_page1.json()
    assert len(data1["results"]) == 2
    # Ordered newest first: t3, then t2
    assert data1["results"][0]["id"] == str(t3.id)
    assert data1["results"][1]["id"] == str(t2.id)
    assert data1["next"] is not None

    # Page 2: follow next cursor
    res_page2 = passenger.get(data1["next"])
    assert res_page2.status_code == 200
    data2 = res_page2.json()
    assert len(data2["results"]) == 1
    assert data2["results"][0]["id"] == str(t1.id)
