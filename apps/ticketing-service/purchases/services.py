"""Purchase write path (task T-08; design §6.1 and §6.2).

Takes plain data, never the HTTP request. Raises domain exceptions; returns a `PurchaseOutcome`
that the view maps to a response.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import structlog
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from metro_common.events import EventEnvelope, TicketPurchasedV1

from common.clock import Clock, default_clock
from outbox.services import enqueue
from purchases import selectors
from purchases.clients import PaymentClient, PaymentOutcome
from purchases.exceptions import (
    PAYMENT_DECLINED_CODE,
    PAYMENT_DECLINED_MESSAGE,
    IdempotencyKeyReused,
    PriceChanged,
    TicketTypeNotAvailable,
    TicketTypeNotFound,
)
from purchases.models import Purchase
from ticket_types.models import TicketType
from ticket_types.selectors import find_ticket_type
from tickets.models import Ticket, TicketStateChange

logger = structlog.get_logger(__name__)

PRODUCER = "ticketing-service"
# Fixed namespace so the event id of a purchase is deterministic (design §3, outbox_event).
TICKET_PURCHASED_NAMESPACE = uuid.UUID("5a1d1c2e-4b7f-4f2a-9c3e-7d8b6a0f1e21")


@dataclass(frozen=True)
class PurchaseRequest:
    passenger_id: uuid.UUID
    idempotency_key: uuid.UUID
    ticket_type_id: uuid.UUID
    expected_price_cents: int
    payment_method_token: str


@dataclass(frozen=True)
class PurchaseOutcome:
    purchase_id: uuid.UUID
    http_status: int
    body: dict[str, Any]


def request_fingerprint(request: PurchaseRequest) -> str:
    canonical = json.dumps(
        {
            "expectedPriceCents": request.expected_price_cents,
            "paymentMethodToken": request.payment_method_token,
            "ticketTypeId": str(request.ticket_type_id),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_purchase(
    request: PurchaseRequest,
    *,
    payment_client: PaymentClient,
    correlation_id: str,
    clock: Clock = default_clock,
) -> PurchaseOutcome:
    fingerprint = request_fingerprint(request)

    # The key is resolved before any business check, so a replay still works after the type is retired (N-07).
    existing = selectors.find_purchase_by_key(request.passenger_id, request.idempotency_key)
    if existing is not None:
        return _resolve_existing(existing, fingerprint)

    ticket_type = _purchasable_ticket_type(request)

    now = clock.now()
    try:
        with transaction.atomic():
            purchase = Purchase.objects.create(
                passenger_id=request.passenger_id,
                idempotency_key=request.idempotency_key,
                request_fingerprint=fingerprint,
                ticket_type=ticket_type,
                terms_snapshot=ticket_type.terms,
                price_cents=ticket_type.price_cents,
                currency=ticket_type.currency,
                payment_method_token=request.payment_method_token,
                next_attempt_at=now + timedelta(seconds=settings.PURCHASE_LEASE_SECONDS),
                correlation_id=correlation_id,
            )
    except IntegrityError:
        # A concurrent request with the same key won the insert (uq_purchases_passenger_key).
        existing = selectors.find_purchase_by_key(request.passenger_id, request.idempotency_key)
        if existing is None:
            raise
        return _resolve_existing(existing, fingerprint)

    logger.info("purchase_created", purchase_id=str(purchase.id), ticket_type_id=str(ticket_type.id))

    # One payment attempt in the request, outside any transaction (N-09). The purchase id is the payment key (N-05).
    result = payment_client.pay(
        idempotency_key=purchase.id,
        amount_cents=purchase.price_cents,
        currency=purchase.currency,
        payment_method_token=purchase.payment_method_token,
    )
    if result.outcome is PaymentOutcome.APPROVED and result.payment_id is not None:
        purchase = finalize_approved(purchase.id, payment_id=result.payment_id, clock=clock)
    elif result.outcome is PaymentOutcome.DECLINED:
        purchase = finalize_declined(purchase.id, clock=clock)
    else:
        purchase = _schedule_retry(purchase.id, clock=clock)
    return outcome_for(purchase)


def finalize_approved(purchase_id: uuid.UUID, *, payment_id: str, clock: Clock = default_clock) -> Purchase:
    """Issue exactly one ticket for an approved payment. Lock, check, write; idempotent (design §6.2)."""
    with transaction.atomic():
        purchase = Purchase.objects.select_for_update().get(id=purchase_id)
        if purchase.status != Purchase.Status.PENDING:
            return purchase

        now = clock.now()
        ticket = Ticket.objects.create(
            purchase=purchase,
            passenger_id=purchase.passenger_id,
            ticket_type_id=purchase.ticket_type_id,
            terms_snapshot=purchase.terms_snapshot,  # the purchase's snapshot, not the live type (PUR-FR-17)
            price_cents=purchase.price_cents,
            currency=purchase.currency,
            status=Ticket.Status.ISSUED,
            issued_at=now,
        )
        TicketStateChange.objects.create(
            ticket=ticket,
            from_status=None,
            to_status=Ticket.Status.ISSUED,
            reason=TicketStateChange.Reason.PURCHASE,
            correlation_id=purchase.correlation_id,
        )

        purchase.status = Purchase.Status.COMPLETED
        purchase.payment_id = payment_id
        purchase.completed_at = now
        purchase.response_status = 201
        purchase.response_body = selectors.purchase_body(purchase, ticket_id=ticket.id)
        purchase.save(
            update_fields=["status", "payment_id", "completed_at", "response_status", "response_body", "updated_at"]
        )

        enqueue(
            envelope=_ticket_purchased_envelope(purchase, ticket, issued_at=now),
            routing_key=TicketPurchasedV1.ROUTING_KEY,
        )

    logger.info("purchase_completed", purchase_id=str(purchase.id), ticket_id=str(ticket.id))
    return purchase


def finalize_declined(purchase_id: uuid.UUID, *, clock: Clock = default_clock) -> Purchase:
    """Terminal failure: no ticket, no event (PUR-FR-10)."""
    with transaction.atomic():
        purchase = Purchase.objects.select_for_update().get(id=purchase_id)
        if purchase.status != Purchase.Status.PENDING:
            return purchase
        purchase.status = Purchase.Status.FAILED
        purchase.failure_code = PAYMENT_DECLINED_CODE
        purchase.completed_at = clock.now()
        purchase.response_status = 422
        purchase.response_body = {"error": {"code": PAYMENT_DECLINED_CODE, "message": PAYMENT_DECLINED_MESSAGE}}
        purchase.save(
            update_fields=["status", "failure_code", "completed_at", "response_status", "response_body", "updated_at"]
        )
    logger.info("purchase_failed", purchase_id=str(purchase.id), failure_code=PAYMENT_DECLINED_CODE)
    return purchase


def outcome_for(purchase: Purchase) -> PurchaseOutcome:
    if purchase.status != Purchase.Status.PENDING and purchase.response_status is not None:
        return PurchaseOutcome(purchase.id, purchase.response_status, dict(purchase.response_body or {}))
    return PurchaseOutcome(purchase.id, 202, selectors.purchase_body(purchase))


def _resolve_existing(purchase: Purchase, fingerprint: str) -> PurchaseOutcome:
    if purchase.request_fingerprint != fingerprint:
        raise IdempotencyKeyReused()
    return outcome_for(purchase)


def _purchasable_ticket_type(request: PurchaseRequest) -> TicketType:
    ticket_type = find_ticket_type(request.ticket_type_id)
    if ticket_type is None:
        raise TicketTypeNotFound()
    if ticket_type.status != TicketType.Status.ACTIVE:
        raise TicketTypeNotAvailable()
    if ticket_type.price_cents != request.expected_price_cents:
        raise PriceChanged()
    return ticket_type


def _schedule_retry(purchase_id: uuid.UUID, *, clock: Clock) -> Purchase:
    """Uncertain outcome: stay PENDING for the reconciler (PUR-FR-11). The reconciler itself is not built yet (OQ-02)."""
    now = clock.now()
    Purchase.objects.filter(id=purchase_id, status=Purchase.Status.PENDING).update(
        attempts=F("attempts") + 1,
        last_attempt_at=now,
        next_attempt_at=now + timedelta(seconds=settings.PURCHASE_RETRY_AFTER_SECONDS),
        updated_at=now,
    )
    return Purchase.objects.get(id=purchase_id)


def _ticket_purchased_envelope(purchase: Purchase, ticket: Ticket, *, issued_at: datetime) -> EventEnvelope:
    payload = TicketPurchasedV1(
        purchase_id=purchase.id,
        ticket_id=ticket.id,
        passenger_id=purchase.passenger_id,
        ticket_type_id=purchase.ticket_type_id,
        price_cents=purchase.price_cents,
        currency=purchase.currency,
        issued_at=issued_at,
    )
    return EventEnvelope(
        event_id=uuid.uuid5(TICKET_PURCHASED_NAMESPACE, f"TicketPurchased:{purchase.id}"),
        type=TicketPurchasedV1.TYPE,
        version=TicketPurchasedV1.VERSION,
        producer=PRODUCER,
        occurred_at=issued_at,
        correlation_id=purchase.correlation_id,
        payload=payload.model_dump(mode="json", by_alias=True),
    )
