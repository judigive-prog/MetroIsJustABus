import uuid
from typing import Any

from common.clock import to_iso
from purchases.models import Purchase


def find_purchase_by_key(passenger_id: uuid.UUID, idempotency_key: uuid.UUID) -> Purchase | None:
    return Purchase.objects.filter(passenger_id=passenger_id, idempotency_key=idempotency_key).first()


def find_purchase_for_passenger(purchase_id: uuid.UUID, passenger_id: uuid.UUID) -> Purchase | None:
    """Another passenger's purchase is reported as not found (PUR-FR-13)."""
    return Purchase.objects.filter(id=purchase_id, passenger_id=passenger_id).first()


def purchase_body(purchase: Purchase, *, ticket_id: uuid.UUID | None = None) -> dict[str, Any]:
    """Public representation of a purchase (design §5.1)."""
    body: dict[str, Any] = {
        "id": str(purchase.id),
        "status": purchase.status,
        "ticketTypeId": str(purchase.ticket_type_id),
        "priceCents": purchase.price_cents,
        "currency": purchase.currency,
        "createdAt": to_iso(purchase.created_at),
    }
    if purchase.status == Purchase.Status.COMPLETED:
        if ticket_id is None:
            ticket_id = purchase.tickets.values_list("id", flat=True).get()
        body["ticketId"] = str(ticket_id)
        if purchase.completed_at is not None:
            body["completedAt"] = to_iso(purchase.completed_at)
    if purchase.status == Purchase.Status.FAILED:
        body["failureCode"] = purchase.failure_code
    return body
