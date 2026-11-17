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
from subscriptions.models import EntityType
from subscriptions.selectors import find_active_subscriptions_for_entities

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RelevantChangeEvent:
    """Represents an incoming domain event triggering notifications (FR-063, FR-064, FR-065)."""

    event_id: uuid.UUID
    change_type: str
    entity_type: str
    entity_id: str
    title: str
    body: str
    occurred_at: datetime.datetime | None = None
    correlation_id: str = ""
    related_entities: Sequence[tuple[str, str]] = field(default_factory=tuple)
    line_id: str = ""
    stop_ids: Sequence[str] = field(default_factory=tuple)


def expand_affected_entities(
    event: RelevantChangeEvent,
    topology_resolver: Callable[[str, str], Sequence[tuple[str, str]]] | None = None,
) -> set[tuple[str, str]]:
    """Expand event entity according to hierarchy coverage rules (FR-065).

    - Line subscriptions cover stops and trips on that line.
    - Stop subscriptions cover trips serving that stop.
    - Direct subscriptions cover the event entity directly.
    - Overlapping matches are collapsed to distinct entities.
    """
    entities: set[tuple[str, str]] = {(event.entity_type, event.entity_id)}

    if event.line_id:
        entities.add((EntityType.LINE, event.line_id))

    if event.stop_ids:
        for stop_id in event.stop_ids:
            entities.add((EntityType.STOP, stop_id))

    if event.related_entities:
        for entity in event.related_entities:
            entities.add(entity)

    if topology_resolver:
        for entity in topology_resolver(event.entity_type, event.entity_id):
            entities.add(entity)

    return entities


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
    topology_resolver: Callable[[str, str], Sequence[tuple[str, str]]] | None = None,
) -> list[NotificationRecord]:
    """Identify affected passengers and dispatch notifications across configured channels (FR-063).

    Hierarchy Expansion and Overlapping Deduplication (FR-065):
    - Subscriptions to a line cover that line's stops and trips.
    - Subscriptions to a stop cover trips serving that stop.
    - Overlapping subscriptions for the same passenger produce exactly ONE notification.

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

    entities = expand_affected_entities(event, topology_resolver=topology_resolver)
    active_subscriptions = find_active_subscriptions_for_entities(list(entities), at_time=event.occurred_at)
    affected_passengers = set(active_subscriptions.values_list("passenger_id", flat=True))

    logger.info(
        "processing_relevant_change",
        event_id=str(event.event_id),
        change_type=event.change_type,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        matched_entity_count=len(entities),
        affected_passenger_count=len(affected_passengers),
    )

    records: list[NotificationRecord] = []
    now = datetime.datetime.now(datetime.UTC)

    for passenger_id in affected_passengers:
        for channel in (NotificationChannel.IN_APP, NotificationChannel.EMAIL):
            if not is_channel_enabled_for_passenger(
                passenger_id,
                channel,
                event.change_type,
                at_time=event.occurred_at,
            ):
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
