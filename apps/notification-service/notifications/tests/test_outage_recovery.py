import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest
from django.core.management import call_command
from metro_common.events.envelope import EventEnvelope

from inbox.models import InboxEvent, InboxNotification
from notifications.events.consumer import NotificationEventConsumer
from notifications.models import DeliveryStatus, NotificationRecord
from preferences.models import ChangeType
from subscriptions.models import EntityType, Subscription


class SimulatedAmqpChannel:
    """In-memory AMQP channel simulating RabbitMQ queue retention and DLQ behavior."""

    def __init__(self) -> None:
        self.queues: dict[str, list[dict[str, Any]]] = {
            "notification-service.events": [],
            "notification-service.events.dlq": [],
        }
        self.dlq_name = "notification-service.events.dlq"
        self.acked_tags: list[int] = []
        self.nacked_tags: list[int] = []
        self.delivery_counter = 0
        self.is_open = True
        self.is_closed = False
        self.consumer_callback: Any = None

    def exchange_declare(self, exchange: str, exchange_type: str = "topic", durable: bool = True) -> None:
        pass

    def queue_declare(self, queue: str, durable: bool = True, arguments: dict[str, Any] | None = None) -> None:
        if queue not in self.queues:
            self.queues[queue] = []

    def queue_bind(self, queue: str, exchange: str, routing_key: str) -> None:
        if queue not in self.queues:
            self.queues[queue] = []

    def basic_publish(
        self,
        exchange: str,
        routing_key: str,
        body: bytes | str,
        properties: Any = None,
    ) -> None:
        target_queue = "notification-service.events"
        if target_queue not in self.queues:
            self.queues[target_queue] = []
        self.delivery_counter += 1
        raw_body = body.encode("utf-8") if isinstance(body, str) else body
        self.queues[target_queue].append(
            {
                "delivery_tag": self.delivery_counter,
                "body": raw_body,
                "properties": properties,
            }
        )

    def basic_get(self, queue: str, auto_ack: bool = False) -> tuple[Any, Any, bytes | None]:
        if queue not in self.queues or not self.queues[queue]:
            return None, None, None
        msg = self.queues[queue].pop(0)
        method_frame = type("MethodFrame", (), {"delivery_tag": msg["delivery_tag"]})()
        properties = msg.get("properties")
        body = msg["body"]
        if auto_ack:
            self.acked_tags.append(msg["delivery_tag"])
        return method_frame, properties, body

    def basic_ack(self, delivery_tag: int) -> None:
        self.acked_tags.append(delivery_tag)

    def basic_nack(self, delivery_tag: int, requeue: bool = False) -> None:
        self.nacked_tags.append(delivery_tag)
        if not requeue:
            self.queues[self.dlq_name].append(
                {
                    "delivery_tag": delivery_tag,
                    "dlq_routed": True,
                }
            )

    def basic_qos(self, prefetch_count: int = 10) -> None:
        pass

    def basic_consume(self, queue: str, on_message_callback: Any) -> None:
        self.consumer_callback = on_message_callback

    def stop_consuming(self) -> None:
        pass

    def close(self) -> None:
        self.is_open = False
        self.is_closed = True


def _make_envelope(
    event_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
    occurred_at: datetime | None = None,
) -> str:
    env = EventEnvelope(
        event_id=event_id,
        type=event_type,
        version=1,
        producer="core-backend",
        occurred_at=occurred_at or datetime.now(UTC),
        correlation_id=str(uuid.uuid4()),
        payload=payload,
    )
    return env.model_dump_json(by_alias=True)


@pytest.mark.django_db
@pytest.mark.req("NFR-021")
def test_notification_events_retained_in_broker_during_outage() -> None:
    """NFR-021: Events are retained in the broker while notification component is unavailable,

    and notifications are delivered after recovery.
    """
    passenger_id = uuid.uuid4()
    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-yellow",
        active=True,
    )

    channel = SimulatedAmqpChannel()
    consumer = NotificationEventConsumer(channel=channel)
    consumer.setup_topology()

    # Step 1: Outage simulation - Consumer is offline/stopped.
    # Disruption event is published to the broker while consumer is down.
    event_id = uuid.uuid4()
    payload = {
        "changeType": ChangeType.DISRUPTION,
        "entityType": EntityType.LINE,
        "entityId": "line-yellow",
        "title": "Yellow Line Signal Failure",
        "description": "Suspended service between North and South.",
    }
    raw_message = _make_envelope(event_id, "DisruptionReported", payload)
    channel.basic_publish(
        exchange="metro.events",
        routing_key="core.disruptions.created",
        body=raw_message,
    )

    # Verify event is retained in the broker queue
    assert len(channel.queues["notification-service.events"]) == 1

    # Verify database has received NO notifications or processed events during outage
    assert InboxEvent.objects.count() == 0
    assert InboxNotification.objects.count() == 0
    assert NotificationRecord.objects.count() == 0

    # Step 2: Recovery simulation - Notification component restarts / recovers
    processed = consumer.consume_batch(max_messages=10)
    assert processed == 1

    # Broker queue is now drained and acknowledged
    assert len(channel.queues["notification-service.events"]) == 0
    assert len(channel.acked_tags) == 1

    # Notification component reconciled the event into inbox_event
    inbox_event = InboxEvent.objects.get(event_id=event_id)
    assert inbox_event.event_type == "DisruptionReported"
    assert inbox_event.producer == "core-backend"

    # Subscriber received logical notifications
    inbox_notif = InboxNotification.objects.get(passenger_id=passenger_id, event_id=event_id)
    assert inbox_notif.title == "Yellow Line Signal Failure"
    assert inbox_notif.change_type == ChangeType.DISRUPTION
    assert inbox_notif.entity_id == "line-yellow"

    records = NotificationRecord.objects.filter(event_id=event_id, passenger_id=passenger_id)
    assert records.count() == 2  # IN_APP, EMAIL
    for rec in records:
        assert rec.status == DeliveryStatus.DELIVERED


@pytest.mark.django_db
@pytest.mark.req("NFR-021")
def test_recovery_reconciles_multiple_retained_events_without_loss() -> None:
    """NFR-021: Multiple events accumulated during component outage are all reconciled

    without loss once the component recovers.
    """
    passenger_id = uuid.uuid4()
    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-red",
        active=True,
    )

    channel = SimulatedAmqpChannel()
    consumer = NotificationEventConsumer(channel=channel)
    consumer.setup_topology()

    # Outage: Accumulate 3 events while consumer is offline
    event_ids = [uuid.uuid4() for _ in range(3)]
    for i, ev_id in enumerate(event_ids):
        payload = {
            "changeType": ChangeType.DISRUPTION,
            "entityType": EntityType.LINE,
            "entityId": "line-red",
            "title": f"Incident #{i + 1} on Red Line",
            "description": f"Incident description {i + 1}",
        }
        channel.basic_publish(
            exchange="metro.events",
            routing_key=f"core.disruptions.{i}",
            body=_make_envelope(ev_id, "DisruptionReported", payload),
        )

    # 3 messages waiting in broker queue
    assert len(channel.queues["notification-service.events"]) == 3
    assert InboxEvent.objects.count() == 0

    # Component recovers
    processed = consumer.consume_batch(max_messages=10)
    assert processed == 3
    assert len(channel.acked_tags) == 3

    # All 3 events reconciled in database
    assert InboxEvent.objects.count() == 3
    assert InboxNotification.objects.filter(passenger_id=passenger_id).count() == 3
    assert NotificationRecord.objects.filter(passenger_id=passenger_id).count() == 6  # 3 * 2 channels


@pytest.mark.django_db
@pytest.mark.req("NFR-021")
def test_redelivery_after_recovery_does_not_duplicate_notifications() -> None:
    """NFR-021 & conventions.md: Redelivery of a retained event after recovery

    is deduplicated via inbox_event and produces no duplicate effects.
    """
    passenger_id = uuid.uuid4()
    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.STOP,
        entity_id="stop-central",
        active=True,
    )

    channel = SimulatedAmqpChannel()
    consumer = NotificationEventConsumer(channel=channel)

    event_id = uuid.uuid4()
    payload = {
        "changeType": ChangeType.SCHEDULE_CHANGE,
        "entityType": EntityType.STOP,
        "entityId": "stop-central",
        "title": "Central Stop Schedule Updated",
        "description": "Timetable revised for platform 2.",
    }
    raw_message = _make_envelope(event_id, "ScheduleChanged", payload)

    # 1. First delivery
    channel.basic_publish(
        exchange="metro.events",
        routing_key="core.schedule.changed",
        body=raw_message,
    )
    consumer.consume_batch(max_messages=5)

    assert InboxEvent.objects.filter(event_id=event_id).count() == 1
    assert InboxNotification.objects.filter(passenger_id=passenger_id).count() == 1
    assert NotificationRecord.objects.filter(passenger_id=passenger_id).count() == 2

    # 2. Duplicate redelivery of the same event
    channel.basic_publish(
        exchange="metro.events",
        routing_key="core.schedule.changed",
        body=raw_message,
    )
    processed = consumer.consume_batch(max_messages=5)
    assert processed == 1

    # Verified: exactly 1 ack for first, 1 ack for duplicate replay
    assert len(channel.acked_tags) == 2
    # Verified: NO duplicate inbox events or notifications created
    assert InboxEvent.objects.filter(event_id=event_id).count() == 1
    assert InboxNotification.objects.filter(passenger_id=passenger_id).count() == 1
    assert NotificationRecord.objects.filter(passenger_id=passenger_id).count() == 2


@pytest.mark.django_db
@pytest.mark.req("NFR-021")
def test_poison_message_routed_to_dlq_does_not_block_retained_events() -> None:
    """NFR-021 & conventions.md: Poison messages are nacked to DLQ and do not block valid retained messages."""
    passenger_id = uuid.uuid4()
    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-orange",
        active=True,
    )

    channel = SimulatedAmqpChannel()
    consumer = NotificationEventConsumer(channel=channel, raise_on_error=False)

    # 1. Valid message 1
    ev_1 = uuid.uuid4()
    msg_1 = _make_envelope(
        ev_1,
        "DisruptionReported",
        {
            "changeType": ChangeType.DISRUPTION,
            "entityType": EntityType.LINE,
            "entityId": "line-orange",
            "title": "Orange Line Incident 1",
            "description": "Minor delay",
        },
    )
    channel.basic_publish(exchange="metro.events", routing_key="core.disruptions.1", body=msg_1)

    # 2. Poison message (invalid JSON / malformed payload)
    poison_msg = "{invalid_json_corrupted_payload"
    channel.basic_publish(exchange="metro.events", routing_key="core.disruptions.bad", body=poison_msg)

    # 3. Valid message 2
    ev_2 = uuid.uuid4()
    msg_2 = _make_envelope(
        ev_2,
        "DisruptionReported",
        {
            "changeType": ChangeType.DISRUPTION,
            "entityType": EntityType.LINE,
            "entityId": "line-orange",
            "title": "Orange Line Incident 2",
            "description": "Resolved",
        },
    )
    channel.basic_publish(exchange="metro.events", routing_key="core.disruptions.2", body=msg_2)

    # Process all retained messages upon recovery
    processed = consumer.consume_batch(max_messages=10)
    assert processed == 3

    # Valid messages were acknowledged
    assert len(channel.acked_tags) == 2
    # Poison message was nacked without requeue and routed to DLQ
    assert len(channel.nacked_tags) == 1
    assert len(channel.queues["notification-service.events.dlq"]) == 1

    # Both valid events were successfully reconciled in the database
    assert InboxEvent.objects.filter(event_id=ev_1).exists()
    assert InboxEvent.objects.filter(event_id=ev_2).exists()
    assert InboxNotification.objects.filter(passenger_id=passenger_id).count() == 2


@pytest.mark.django_db
@pytest.mark.req("NFR-021")
def test_consume_events_management_command_reconciliation() -> None:
    """NFR-021: Management command consume_events runs batch reconciliation of retained events."""
    passenger_id = uuid.uuid4()
    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-silver",
        active=True,
    )

    channel = SimulatedAmqpChannel()
    ev_id = uuid.uuid4()
    payload = {
        "changeType": ChangeType.DISRUPTION,
        "entityType": EntityType.LINE,
        "entityId": "line-silver",
        "title": "Silver Line Express",
        "description": "Track maintenance",
    }
    channel.basic_publish(
        exchange="metro.events",
        routing_key="core.disruptions.silver",
        body=_make_envelope(ev_id, "DisruptionReported", payload),
    )

    with patch(
        "notifications.management.commands.consume_events.NotificationEventConsumer",
        return_value=NotificationEventConsumer(channel=channel),
    ):
        call_command("consume_events", batch=5)

    assert InboxEvent.objects.filter(event_id=ev_id).exists()
    assert InboxNotification.objects.filter(passenger_id=passenger_id, event_id=ev_id).exists()
