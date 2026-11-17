import datetime
import uuid
from dataclasses import dataclass, field
from typing import Sequence

import structlog
from django.db import transaction

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


def process_relevant_change(event: RelevantChangeEvent) -> list[NotificationRecord]:
    """Identify affected passengers and dispatch notifications across configured channels (FR-063).

    1. Resolves affected entities from the event (primary entity + related entities).
    2. Finds active subscriptions covering those entities.
    3. Identifies the distinct set of affected passengers (excluding unrelated passengers).
    4. Evaluates passenger preferences per channel (IN_APP, EMAIL).
    5. Persists in-app notifications into the passenger inbox and records delivery.
    """
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

    created_records: list[NotificationRecord] = []
    now = datetime.datetime.now(datetime.UTC)

    with transaction.atomic():
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

                if channel == NotificationChannel.IN_APP:
                    create_inbox_notification(
                        passenger_id=passenger_id,
                        event_id=event.event_id,
                        title=event.title,
                        body=event.body,
                        change_type=event.change_type,
                        entity_type=event.entity_type,
                        entity_id=event.entity_id,
                    )

                record, created = NotificationRecord.objects.get_or_create(
                    event_id=event.event_id,
                    passenger_id=passenger_id,
                    channel=channel,
                    defaults={
                        "status": DeliveryStatus.DELIVERED,
                        "attempts": 1,
                        "last_attempt_at": now,
                    },
                )
                created_records.append(record)

    logger.info(
        "relevant_change_processed",
        event_id=str(event.event_id),
        dispatched_records_count=len(created_records),
    )
    return created_records
