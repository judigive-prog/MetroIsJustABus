import uuid

from django.db.models import QuerySet

from notifications.models import DeliveryStatus, NotificationRecord


def get_notification_records_for_event(event_id: uuid.UUID) -> QuerySet[NotificationRecord]:
    """Retrieve all notification records created for a specific event."""
    return NotificationRecord.objects.filter(event_id=event_id).order_by("created_at")


def get_notification_records_for_passenger(passenger_id: uuid.UUID) -> QuerySet[NotificationRecord]:
    """Retrieve all notification records for a specific passenger."""
    return NotificationRecord.objects.filter(passenger_id=passenger_id).order_by("-created_at")


def list_delivered_passengers_for_event(event_id: uuid.UUID) -> set[uuid.UUID]:
    """Return the set of unique passenger IDs who received a notification for an event."""
    return set(
        NotificationRecord.objects.filter(
            event_id=event_id,
            status=DeliveryStatus.DELIVERED,
        )
        .values_list("passenger_id", flat=True)
        .distinct()
    )


def is_notification_delivered(event_id: uuid.UUID, passenger_id: uuid.UUID, channel: str) -> bool:
    """Check if a notification has already been successfully delivered for the given passenger and channel (FR-066)."""
    return NotificationRecord.objects.filter(
        event_id=event_id,
        passenger_id=passenger_id,
        channel=channel,
        status=DeliveryStatus.DELIVERED,
    ).exists()
