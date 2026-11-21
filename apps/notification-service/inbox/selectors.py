import uuid

from django.db.models import QuerySet

from inbox.models import InboxEvent, InboxNotification


def list_passenger_notifications(passenger_id: uuid.UUID, unread_only: bool = False) -> QuerySet[InboxNotification]:
    qs = InboxNotification.objects.filter(passenger_id=passenger_id)
    if unread_only:
        qs = qs.filter(read_at__isnull=True)
    return qs.order_by("-created_at")


def get_passenger_notification(passenger_id: uuid.UUID, notification_id: uuid.UUID) -> InboxNotification | None:
    return InboxNotification.objects.filter(id=notification_id, passenger_id=passenger_id).first()


def count_unread_notifications(passenger_id: uuid.UUID) -> int:
    return InboxNotification.objects.filter(passenger_id=passenger_id, read_at__isnull=True).count()


def is_event_processed(event_id: uuid.UUID) -> bool:
    """Check if an event has already been recorded and processed in the inbox_event table."""
    return InboxEvent.objects.filter(event_id=event_id).exists()


def get_inbox_event(event_id: uuid.UUID) -> InboxEvent | None:
    """Retrieve an inbox event by event_id."""
    return InboxEvent.objects.filter(event_id=event_id).first()
