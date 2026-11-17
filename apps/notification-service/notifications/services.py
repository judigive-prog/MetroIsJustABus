import datetime
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import structlog
from django.db import IntegrityError, transaction

from inbox.services import create_inbox_notification
from notifications.models import DeliveryStatus, NotificationRecord
from preferences.models import NotificationChannel
from preferences.selectors import is_channel_enabled_for_passenger
from subscriptions.selectors import find_active_subscriptions_for_entities

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RelevantChangeEvent:
    """Represents an incoming domain event triggering notifications (FR-063, FR-064)."""

    event_id: uuid.UUID
    change_type: str
    entity_type: str
    entity_id: str
    title: str
    body: str
    occurred_at: datetime.datetime | None = None
    correlation_id: str = ""
    related_entities: Sequence[tuple[str, str]] = field(default_factory=tuple)


def default_in_app_dispatcher(event: RelevantChangeEvent, passenger_id: uuid.UUID) -> None:
    """Deliver in-app notification by persisting into the passenger inbox (FR-067)."""
    create_inbox_notification(
        passenger_id=passenger_id,
        event_id=event.event_id,
        title=event.title,
        body=event.body,
        change_type=event.change_type,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
    )


def default_email_dispatcher(event: RelevantChangeEvent, passenger_id: uuid.UUID) -> None:
    """Deliver email notification (A-06 sandboxed email delivery)."""
    logger.info(
        "email_notification_dispatched",
        passenger_id=str(passenger_id),
        event_id=str(event.event_id),
        title=event.title,
    )


DEFAULT_DISPATCHERS: dict[str, Callable[[RelevantChangeEvent, uuid.UUID], None]] = {
    NotificationChannel.IN_APP: default_in_app_dispatcher,
    NotificationChannel.EMAIL: default_email_dispatcher,
}


def process_relevant_change(
    event: RelevantChangeEvent,
    dispatchers: dict[str, Callable[[RelevantChangeEvent, uuid.UUID], None]] | None = None,
    raise_on_failure: bool = False,
) -> list[NotificationRecord]:
    """Identify affected passengers and dispatch notifications across configured channels (FR-063).

    Deduplication and Resilience (FR-066):
    - Checks logical delivery boundary (event_id, passenger_id, channel).
    - If already DELIVERED, skips delivery to prevent duplicate notifications.
    - If previously FAILED, retries delivery incrementing attempt count.
    - Records failed delivery status and error details upon failure.
    - Preserves deduplication boundary even after simulated response failures.
    """
    active_dispatchers = dict(DEFAULT_DISPATCHERS)
    if dispatchers:
        active_dispatchers.update(dispatchers)

    entities: list[tuple[str, str]] = [(event.entity_type, event.entity_id)]
    if event.related_entities:
        entities.extend(event.related_entities)

    active_subscriptions = find_active_subscriptions_for_entities(entities)
    affected_passengers = set(active_subscriptions.values_list("passenger_id", flat=True))

    logger.info(
        "processing_relevant_change",
        event_id=str(event.event_id),
        change_type=event.change_type,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        affected_passenger_count=len(affected_passengers),
    )

    records: list[NotificationRecord] = []
    now = datetime.datetime.now(datetime.UTC)

    for passenger_id in affected_passengers:
        for channel in (NotificationChannel.IN_APP, NotificationChannel.EMAIL):
            if not is_channel_enabled_for_passenger(passenger_id, channel, event.change_type):
                logger.debug(
                    "channel_skipped_by_preference",
                    passenger_id=str(passenger_id),
                    channel=channel,
                    change_type=event.change_type,
                )
                continue

            record = NotificationRecord.objects.filter(
                event_id=event.event_id,
                passenger_id=passenger_id,
                channel=channel,
            ).first()

            # Deduplication boundary check (FR-066)
            if record is not None and record.status == DeliveryStatus.DELIVERED:
                logger.info(
                    "duplicate_notification_skipped",
                    event_id=str(event.event_id),
                    passenger_id=str(passenger_id),
                    channel=channel,
                )
                records.append(record)
                continue

            if record is None:
                record = NotificationRecord(
                    event_id=event.event_id,
                    passenger_id=passenger_id,
                    channel=channel,
                    status=DeliveryStatus.PENDING,
                    attempts=0,
                )

            record.attempts += 1
            record.last_attempt_at = now

            dispatcher = active_dispatchers.get(channel)
            delivery_error: Exception | None = None
            if dispatcher:
                try:
                    with transaction.atomic():
                        dispatcher(event, passenger_id)
                except Exception as exc:
                    delivery_error = exc

            if delivery_error is None:
                record.status = DeliveryStatus.DELIVERED
                record.error_message = ""
                try:
                    record.save()
                except IntegrityError:
                    record = NotificationRecord.objects.get(
                        event_id=event.event_id,
                        passenger_id=passenger_id,
                        channel=channel,
                    )
            else:
                record.status = DeliveryStatus.FAILED
                record.error_message = str(delivery_error)
                try:
                    record.save()
                except IntegrityError:
                    record = NotificationRecord.objects.get(
                        event_id=event.event_id,
                        passenger_id=passenger_id,
                        channel=channel,
                    )
                logger.warning(
                    "notification_delivery_failed",
                    event_id=str(event.event_id),
                    passenger_id=str(passenger_id),
                    channel=channel,
                    attempt=record.attempts,
                    error=str(delivery_error),
                )
                if raise_on_failure:
                    raise delivery_error

            records.append(record)

    logger.info(
        "relevant_change_processed",
        event_id=str(event.event_id),
        dispatched_records_count=len(records),
    )
    return records
