import uuid

from django.db.models import QuerySet

from tickets.models import Ticket, ValidationAttempt


def list_passenger_tickets(passenger_id: uuid.UUID) -> QuerySet[Ticket]:
    """Return all tickets associated with a passenger's account (FR-034)."""
    return (
        Ticket.objects.filter(passenger_id=passenger_id)
        .select_related("ticket_type")
        .prefetch_related("validation_attempts", "state_changes")
        .order_by("-issued_at", "-created_at")
    )


def get_passenger_ticket(ticket_id: uuid.UUID, passenger_id: uuid.UUID) -> Ticket | None:
    """Return a single ticket for a passenger, or None if not found or owned by another (FR-034, FR-102)."""
    return (
        Ticket.objects.filter(id=ticket_id, passenger_id=passenger_id)
        .select_related("ticket_type")
        .prefetch_related("validation_attempts", "state_changes")
        .first()
    )


def get_ticket_validation_history(ticket: Ticket) -> QuerySet[ValidationAttempt]:
    """Return validation attempts for a ticket ordered newest first (FR-034)."""
    return ticket.validation_attempts.all().order_by("-decided_at", "-created_at")
