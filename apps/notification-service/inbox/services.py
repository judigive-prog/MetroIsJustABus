import datetime
import uuid

import structlog
from django.db import transaction

from inbox.exceptions import NotificationNotFound
from inbox.models import InboxNotification
from inbox.selectors import get_passenger_notification

logger = structlog.get_logger(__name__)


def create_inbox_notification(
    passenger_id: uuid.UUID,
    event_id: uuid.UUID,
    title: str,
    body: str,
    change_type: str,
    entity_type: str = "",
    entity_id: str = "",
) -> tuple[InboxNotification, bool]:
    """Create in-app inbox notification for a passenger (FR-067).

    Returns (InboxNotification, created_boolean). Deduplicates per (passenger_id, event_id).
    """
    with transaction.atomic():
        notif, created = InboxNotification.objects.get_or_create(
            passenger_id=passenger_id,
            event_id=event_id,
            defaults={
                "title": title,
                "body": body,
                "change_type": change_type,
                "entity_type": entity_type,
                "entity_id": entity_id,
            },
        )
        if created:
            logger.info(
                "inbox_notification_created",
                passenger_id=str(passenger_id),
                event_id=str(event_id),
                notification_id=str(notif.id),
                change_type=change_type,
            )
        return notif, created


def mark_as_read(passenger_id: uuid.UUID, notification_id: uuid.UUID) -> InboxNotification:
    notif = get_passenger_notification(passenger_id=passenger_id, notification_id=notification_id)
    if not notif:
        raise NotificationNotFound()

    if not notif.read_at:
        notif.read_at = datetime.datetime.now(datetime.UTC)
        notif.save(update_fields=["read_at", "updated_at"])
        logger.info(
            "inbox_notification_marked_read",
            passenger_id=str(passenger_id),
            notification_id=str(notification_id),
        )
    return notif


def mark_all_as_read(passenger_id: uuid.UUID) -> int:
    now = datetime.datetime.now(datetime.UTC)
    updated_count = InboxNotification.objects.filter(
        passenger_id=passenger_id,
        read_at__isnull=True,
    ).update(read_at=now, updated_at=now)
    logger.info("inbox_all_marked_read", passenger_id=str(passenger_id), count=updated_count)
    return updated_count
