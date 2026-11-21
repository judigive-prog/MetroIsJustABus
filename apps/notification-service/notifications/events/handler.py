import datetime
import json
import uuid
from collections.abc import Callable, Sequence
from typing import Any

import structlog
from django.db import transaction

from inbox.selectors import is_event_processed
from inbox.services import record_inbox_event
from notifications.models import NotificationRecord
from notifications.services import RelevantChangeEvent, process_relevant_change
from preferences.models import ChangeType
from subscriptions.models import EntityType

logger = structlog.get_logger(__name__)


def _parse_occurred_at(value: Any) -> datetime.datetime | None:
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _infer_change_type(event_type: str, payload_change_type: str | None) -> str:
    if payload_change_type and payload_change_type in ChangeType.values:
        return payload_change_type

    lower = event_type.lower()
    if "disruption" in lower:
        return ChangeType.DISRUPTION
    if "delay" in lower or "trip" in lower:
        return ChangeType.DELAY
    if "schedule" in lower:
        return ChangeType.SCHEDULE_CHANGE

    return ChangeType.DISRUPTION


def handle_event_message(
    raw_message: bytes | str | dict[str, Any],
    dispatchers: dict[str, Callable[[RelevantChangeEvent, uuid.UUID], None]] | None = None,
    raise_on_failure: bool = False,
    topology_resolver: Callable[[str, str], Sequence[tuple[str, str]]] | None = None,
) -> tuple[bool, str, list[NotificationRecord]]:
    """Parse, deduplicate via inbox_event, and process incoming broker event message (NFR-021, FR-063).

    Returns (success: bool, status: str, records: list[NotificationRecord]).
    """
    if isinstance(raw_message, (bytes, bytearray)):
        raw_message = raw_message.decode("utf-8")
    if isinstance(raw_message, str):
        data = json.loads(raw_message)
    elif isinstance(raw_message, dict):
        data = raw_message
    else:
        raise ValueError(f"Unsupported message type: {type(raw_message)}")

    event_id_raw = data.get("eventId") or data.get("event_id")
    if not event_id_raw:
        raise ValueError("Missing eventId/event_id in event envelope")

    event_id = uuid.UUID(str(event_id_raw))
    event_type = str(data.get("type") or data.get("event_type") or "UnknownEvent")
    producer = str(data.get("producer") or "unknown")
    correlation_id = str(data.get("correlationId") or data.get("correlation_id") or "")
    occurred_at = _parse_occurred_at(data.get("occurredAt") or data.get("occurred_at"))

    payload = data.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}

    # At-least-once broker deduplication via inbox_event (conventions.md)
    if is_event_processed(event_id):
        logger.info(
            "event_already_processed_inbox_event_skipped",
            event_id=str(event_id),
            event_type=event_type,
        )
        return True, "already_processed", []

    # Map payload to RelevantChangeEvent domain model
    raw_change_type = payload.get("changeType") or payload.get("change_type")
    change_type = _infer_change_type(event_type, raw_change_type)

    entity_type = str(payload.get("entityType") or payload.get("entity_type") or EntityType.LINE)
    entity_id = str(payload.get("entityId") or payload.get("entity_id") or "")
    title = str(payload.get("title") or f"{change_type.replace('_', ' ').title()}: {entity_type} {entity_id}")
    body = str(payload.get("body") or payload.get("description") or f"Notice regarding {entity_type} {entity_id}.")

    line_id = str(payload.get("lineId") or payload.get("line_id") or "")
    stop_ids = list(payload.get("stopIds") or payload.get("stop_ids") or [])

    raw_related = payload.get("relatedEntities") or payload.get("related_entities") or []
    related_entities: list[tuple[str, str]] = []
    for item in raw_related:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            related_entities.append((str(item[0]), str(item[1])))

    relevant_event = RelevantChangeEvent(
        event_id=event_id,
        change_type=change_type,
        entity_type=entity_type,
        entity_id=entity_id,
        title=title,
        body=body,
        occurred_at=occurred_at,
        correlation_id=correlation_id,
        related_entities=related_entities,
        line_id=line_id,
        stop_ids=stop_ids,
    )

    with transaction.atomic():
        # 1. Record event in inbox_event table
        record_inbox_event(
            event_id=event_id,
            event_type=event_type,
            producer=producer,
            correlation_id=correlation_id,
            payload=payload,
        )

        # 2. Match subscribers, expand hierarchy, deduplicate, and dispatch notifications
        records = process_relevant_change(
            relevant_event,
            dispatchers=dispatchers,
            raise_on_failure=raise_on_failure,
            topology_resolver=topology_resolver,
        )

    logger.info(
        "event_consumed_and_processed",
        event_id=str(event_id),
        event_type=event_type,
        producer=producer,
        dispatched_records_count=len(records),
    )
    return True, "processed", records
