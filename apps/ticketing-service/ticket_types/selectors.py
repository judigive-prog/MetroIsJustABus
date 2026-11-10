import uuid

from django.db.models import QuerySet

from ticket_types.models import TicketType


def active_ticket_types() -> QuerySet[TicketType]:
    return TicketType.objects.filter(status=TicketType.Status.ACTIVE)


def find_ticket_type(ticket_type_id: uuid.UUID) -> TicketType | None:
    return TicketType.objects.filter(id=ticket_type_id).first()
