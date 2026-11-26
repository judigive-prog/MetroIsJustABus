import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from django.test import RequestFactory
from metro_common.events.envelope import EventEnvelope

from common import health
from inbox.models import InboxEvent, InboxNotification
from notifications.events.consumer import NotificationEventConsumer
from notifications.models import DeliveryStatus, NotificationRecord
from preferences.models import ChangeType, NotificationChannel, NotificationPreference
from subscriptions.models import EntityType, Subscription


class E2EBrokerSimulator:
    """Simulates an AMQP broker with durable topic exchange, durable consumer queues, and DLQ."""

    def __init__(self) -> None:
        self.queues: dict[str, list[dict[str, Any]]] = {
            "notification-service.events": [],
            "notification-service.events.dlq": [],
        }
        self.acked_tags: list[int] = []
        self.nacked_tags: list[int] = []
        self.counter = 0
        self.is_open = True
        self.is_closed = False

    def exchange_declare(self, exchange: str, exchange_type: str = "topic", durable: bool = True) -> None:
        pass

    def queue_declare(self, queue: str, durable: bool = True, arguments: dict[str, Any] | None = None) -> None:
        if queue not in self.queues:
            self.queues[queue] = []

    def queue_bind(self, queue: str, exchange: str, routing_key: str) -> None:
        if queue not in self.queues:
            self.queues[queue] = []

    def publish_envelope(self, routing_key: str, envelope: EventEnvelope) -> None:
        self.counter += 1
        raw_json = envelope.model_dump_json(by_alias=True).encode("utf-8")
        self.queues["notification-service.events"].append(
            {
                "delivery_tag": self.counter,
                "body": raw_json,
                "routing_key": routing_key,
                "enqueued_at": datetime.now(UTC),
            }
        )

    def basic_get(self, queue: str, auto_ack: bool = False) -> tuple[Any, Any, bytes | None]:
        if queue not in self.queues or not self.queues[queue]:
            return None, None, None
        msg = self.queues[queue].pop(0)
        method_frame = type("MethodFrame", (), {"delivery_tag": msg["delivery_tag"]})()
        if auto_ack:
            self.acked_tags.append(msg["delivery_tag"])
        return method_frame, None, msg["body"]

    def basic_ack(self, delivery_tag: int) -> None:
        self.acked_tags.append(delivery_tag)

    def basic_nack(self, delivery_tag: int, requeue: bool = False) -> None:
        self.nacked_tags.append(delivery_tag)
        if not requeue:
            self.queues["notification-service.events.dlq"].append({"delivery_tag": delivery_tag, "routed_to_dlq": True})

    def basic_qos(self, prefetch_count: int = 10) -> None:
        pass

    def basic_consume(self, queue: str, on_message_callback: Any) -> None:
        pass

    def stop_consuming(self) -> None:
        pass

    def close(self) -> None:
        self.is_open = False
        self.is_closed = True


def _create_envelope(
    event_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
    occurred_at: datetime | None = None,
    correlation_id: str | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=event_id,
        type=event_type,
        version=1,
        producer="core-backend",
        occurred_at=occurred_at or datetime.now(UTC),
        correlation_id=correlation_id or str(uuid.uuid4()),
        payload=payload,
    )


@pytest.mark.django_db
@pytest.mark.req("E2E-06", "NFR-020", "NFR-023")
def test_e2e_unrelated_functions_unaffected_during_notification_outage() -> None:
    """E2E-06 / NFR-020 / NFR-023: Verify partial-failure isolation.

    While the notification processing component is stopped/isolated, unrelated functions
    (health probes, subscription consultations, passenger preference updates) remain fully
    operational and do not hang or fail.
    """
    passenger_id = uuid.uuid4()

    # Step 1: Fault injection - Notification consumer is stopped/offline
    broker = E2EBrokerSimulator()
    consumer = NotificationEventConsumer(channel=broker)
    assert consumer._is_consuming is False  # Consumer is offline / stopped

    # Step 2: Unrelated operation 1 - Health probes respond immediately
    factory = RequestFactory()
    live_resp = health.live(factory.get("/health/live"))
    assert live_resp.status_code == 200
    assert json.loads(live_resp.content)["status"] == "ok"

    ready_resp = health.ready(factory.get("/health/ready"))
    assert ready_resp.status_code == 200
    assert json.loads(ready_resp.content)["status"] == "ok"

    # Step 3: Unrelated operation 2 - Passenger creates and manages subscriptions
    sub = Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-metro-1",
        active=True,
    )
    assert sub.id is not None
    assert sub.active is True

    # Step 4: Unrelated operation 3 - Passenger updates notification preferences
    pref, created = NotificationPreference.objects.update_or_create(
        passenger_id=passenger_id,
        channel=NotificationChannel.IN_APP,
        defaults={"enabled": True, "enabled_change_types": [ChangeType.DISRUPTION]},
    )
    assert pref.enabled is True

    # Verified: Outage of event consumer did NOT block or degrade database operations
    assert Subscription.objects.filter(passenger_id=passenger_id).count() == 1
    assert NotificationPreference.objects.filter(passenger_id=passenger_id).count() == 1


@pytest.mark.django_db
@pytest.mark.req("E2E-06", "NFR-021", "NFR-016")
def test_e2e_event_retention_during_outage_and_reconciliation_on_recovery() -> None:
    """E2E-06 / NFR-021: Verify event retention during consumer outage and full reconciliation on recovery.

    1. Passenger subscribes to Line A.
    2. Notification consumer is stopped (simulated container crash / maintenance outage).
    3. Core Backend registers a disruption and publishes DisruptionReported event.
    4. Broker retains the message in durable queue 'notification-service.events'.
    5. Database verifies zero notifications are delivered while offline.
    6. Component recovers: Consumer starts and processes retained batch.
    7. Retained event is reconciled: inbox_event is recorded, InboxNotification and NotificationRecords are created.
    """
    passenger_id = uuid.uuid4()
    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-central",
        active=True,
    )

    broker = E2EBrokerSimulator()
    consumer = NotificationEventConsumer(channel=broker)
    consumer.setup_topology()

    # Step 1: Outage active - consumer is offline.
    event_id = uuid.uuid4()
    correlation_id = str(uuid.uuid4())
    event_occurred_at = datetime.now(UTC)

    envelope = _create_envelope(
        event_id=event_id,
        event_type="DisruptionReported",
        payload={
            "changeType": ChangeType.DISRUPTION,
            "entityType": EntityType.LINE,
            "entityId": "line-central",
            "title": "Central Line Power Outage",
            "description": "Third rail power loss between Central and East.",
        },
        occurred_at=event_occurred_at,
        correlation_id=correlation_id,
    )

    # Core backend publishes event to RabbitMQ
    broker.publish_envelope(routing_key="core.disruptions.created", envelope=envelope)

    # Step 2: Verify broker retention while component is down
    assert len(broker.queues["notification-service.events"]) == 1
    # Verify zero database side-effects in notification service during outage
    assert InboxEvent.objects.count() == 0
    assert InboxNotification.objects.count() == 0
    assert NotificationRecord.objects.count() == 0

    # Step 3: Component recovery - Consumer comes online and processes retained messages
    processed = consumer.consume_batch(max_messages=10)
    assert processed == 1

    # Step 4: Verify reconciliation
    # 4.1 Broker queue is now drained and acknowledged
    assert len(broker.queues["notification-service.events"]) == 0
    assert len(broker.acked_tags) == 1

    # 4.2 InboxEvent was recorded transactionally with correlation ID
    inbox_event = InboxEvent.objects.get(event_id=event_id)
    assert inbox_event.event_type == "DisruptionReported"
    assert inbox_event.correlation_id == correlation_id
    assert inbox_event.producer == "core-backend"

    # 4.3 In-app notification delivered to passenger inbox
    inbox_notif = InboxNotification.objects.get(passenger_id=passenger_id, event_id=event_id)
    assert inbox_notif.title == "Central Line Power Outage"
    assert inbox_notif.change_type == ChangeType.DISRUPTION
    assert inbox_notif.entity_id == "line-central"
    assert inbox_notif.read_at is None

    # 4.4 Delivery records created across configured channels (IN_APP, EMAIL)
    records = list(NotificationRecord.objects.filter(event_id=event_id, passenger_id=passenger_id))
    assert len(records) == 2
    for r in records:
        assert r.status == DeliveryStatus.DELIVERED


@pytest.mark.django_db
@pytest.mark.req("E2E-06", "NFR-022", "FR-066")
def test_e2e_replayed_retained_events_produce_no_duplicate_effects() -> None:
    """E2E-06 / NFR-022 / FR-066: Replaying a retained event after recovery produces no duplicate notifications."""
    passenger_id = uuid.uuid4()
    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-north",
        active=True,
    )

    broker = E2EBrokerSimulator()
    consumer = NotificationEventConsumer(channel=broker)

    event_id = uuid.uuid4()
    envelope = _create_envelope(
        event_id=event_id,
        event_type="DisruptionReported",
        payload={
            "changeType": ChangeType.DISRUPTION,
            "entityType": EntityType.LINE,
            "entityId": "line-north",
            "title": "North Line Delay",
            "description": "Signal maintenance.",
        },
    )

    # 1. First delivery from retained queue
    broker.publish_envelope(routing_key="core.disruptions.created", envelope=envelope)
    consumer.consume_batch(max_messages=5)

    assert InboxEvent.objects.filter(event_id=event_id).count() == 1
    assert InboxNotification.objects.filter(passenger_id=passenger_id, event_id=event_id).count() == 1
    assert NotificationRecord.objects.filter(passenger_id=passenger_id, event_id=event_id).count() == 2

    # 2. Replay duplicate event delivery (e.g. RabbitMQ retry or redelivery)
    broker.publish_envelope(routing_key="core.disruptions.created", envelope=envelope)
    processed = consumer.consume_batch(max_messages=5)
    assert processed == 1

    # Both deliveries were acknowledged to prevent broker queue blockage
    assert len(broker.acked_tags) == 2

    # Strictly NO duplicate rows in database
    assert InboxEvent.objects.filter(event_id=event_id).count() == 1
    assert InboxNotification.objects.filter(passenger_id=passenger_id, event_id=event_id).count() == 1
    assert NotificationRecord.objects.filter(passenger_id=passenger_id, event_id=event_id).count() == 2


@pytest.mark.django_db
@pytest.mark.req("E2E-06", "NFR-021", "NFR-020")
def test_e2e_multiple_events_accumulated_during_extended_outage_reconcile_completely() -> None:
    """E2E-06: Accumulate multiple events across multiple entities during outage and reconcile without loss."""
    # 2 passengers subscribed to different lines
    p1 = uuid.uuid4()
    p2 = uuid.uuid4()

    Subscription.objects.create(passenger_id=p1, entity_type=EntityType.LINE, entity_id="line-1", active=True)
    Subscription.objects.create(passenger_id=p2, entity_type=EntityType.LINE, entity_id="line-2", active=True)

    broker = E2EBrokerSimulator()
    consumer = NotificationEventConsumer(channel=broker)

    # Outage: 3 events published while consumer is offline
    e1_id = uuid.uuid4()
    e2_id = uuid.uuid4()
    e3_id = uuid.uuid4()

    broker.publish_envelope(
        routing_key="core.disruptions.line1",
        envelope=_create_envelope(
            e1_id,
            "DisruptionReported",
            {
                "changeType": ChangeType.DISRUPTION,
                "entityType": EntityType.LINE,
                "entityId": "line-1",
                "title": "Incident Line 1",
            },
        ),
    )
    broker.publish_envelope(
        routing_key="core.schedule.line2",
        envelope=_create_envelope(
            e2_id,
            "ScheduleChanged",
            {
                "changeType": ChangeType.SCHEDULE_CHANGE,
                "entityType": EntityType.LINE,
                "entityId": "line-2",
                "title": "Schedule Revision Line 2",
            },
        ),
    )
    broker.publish_envelope(
        routing_key="core.disruptions.line1_res",
        envelope=_create_envelope(
            e3_id,
            "DisruptionReported",
            {
                "changeType": ChangeType.DISRUPTION,
                "entityType": EntityType.LINE,
                "entityId": "line-1",
                "title": "Resolved Line 1",
            },
        ),
    )

    # Queue holds 3 messages, 0 in database
    assert len(broker.queues["notification-service.events"]) == 3
    assert InboxEvent.objects.count() == 0

    # Component restores
    processed = consumer.consume_batch(max_messages=10)
    assert processed == 3

    # All 3 events reconciled in inbox_event
    assert InboxEvent.objects.count() == 3
    assert InboxEvent.objects.filter(event_id__in=[e1_id, e2_id, e3_id]).count() == 3

    # Passenger 1 received 2 notifications (e1, e3)
    assert InboxNotification.objects.filter(passenger_id=p1).count() == 2

    # Passenger 2 received 1 notification (e2)
    assert InboxNotification.objects.filter(passenger_id=p2).count() == 1
