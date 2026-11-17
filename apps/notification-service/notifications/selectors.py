import uuid

from django.db.models import QuerySet

from notifications.models import NotificationRecord


def get_notification_records_for_event(event_id: uuid.UUID) -> QuerySet[NotificationRecord]:
    """Retrieve all notification records created for a specific event."""
    return NotificationRecord.objects.filter(event_id=event_id).order_by("created_at")


def get_notification_records_for_passenger(passenger_id: uuid.UUID) -> QuerySet[NotificationRecord]:
    """Retrieve all notification records for a specific passenger."""
    return NotificationRecord.objects.filter(passenger_id=passenger_id).order_by("-created_at")


def list_delivered_passengers_for_event(event_id: uuid.UUID) -> set[uuid.UUID]:
    """Return the set of unique passenger IDs who received a notification for an event."""
    return set(NotificationRecord.objects.filter(event_id=event_id).values_list("passenger_id", flat=True).distinct())
