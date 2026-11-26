import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from metro_common.events.envelope import EventEnvelope

from inbox.selectors import list_passenger_notifications
from inbox.services import mark_all_as_read, mark_as_read
from notifications.events.consumer import NotificationEventConsumer
from notifications.models import NotificationRecord
from preferences.models import ChangeType, NotificationChannel, NotificationPreference
from subscriptions.models import EntityType, Subscription


class MockAmqpBroker:
    """In-memory broker simulating topic exchange delivery, durable buffering, and DLQ."""

    def __init__(self) -> None:
        self.queues: dict[str, list[dict[str, Any]]] = {
            "notification-service.events": [],
            "notification-service.events.dlq": [],
        }
        self.acked_tags: list[int] = []
        self.nacked_tags: list[int] = []
        self.counter = 0

    def exchange_declare(self, exchange: str, exchange_type: str = "topic", durable: bool = True) -> None:
        pass

    def queue_declare(self, queue: str, durable: bool = True, arguments: dict[str, Any] | None = None) -> None:
        if queue not in self.queues:
            self.queues[queue] = []

    def queue_bind(self, queue: str, exchange: str, routing_key: str) -> None:
        if queue not in self.queues:
            self.queues[queue] = []

    def publish(self, envelope: EventEnvelope) -> None:
        self.counter += 1
        raw_body = envelope.model_dump_json(by_alias=True).encode("utf-8")
        self.queues["notification-service.events"].append(
            {
                "delivery_tag": self.counter,
                "body": raw_body,
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

    def basic_qos(self, prefetch_count: int = 10) -> None:
        pass

    def basic_consume(self, queue: str, on_message_callback: Any) -> None:
        pass

    def stop_consuming(self) -> None:
        pass

    def close(self) -> None:
        pass


def _make_envelope(
    event_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
    occurred_at: datetime | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=event_id,
        type=event_type,
        version=1,
        producer="core-backend",
        occurred_at=occurred_at or datetime.now(UTC),
        correlation_id=str(uuid.uuid4()),
        payload=payload,
    )


@pytest.mark.django_db
@pytest.mark.req("E2E-05", "FR-063", "FR-065", "FR-066", "FR-067", "FR-068", "FR-069")
def test_e2e_disruption_lifecycle_targeted_notifications_and_deduplication() -> None:
    """E2E-05: Verify subscriptions, staff disruptions, targeted notifications, and deduplication.

    1. Create diverse passenger subscription and preference profiles (line, stop, trip, overlapping, unrelated).
    2. Register a staff disruption on Line 1 affecting Stop 1 and Trip 1.
    3. Update the disruption with revised delay estimates.
    4. Close / resolve the disruption.
    5. Verify targeted recipient set, channel boundaries, inbox history, and zero duplicate deliveries on replay.
    """
    broker = MockAmqpBroker()
    consumer = NotificationEventConsumer(channel=broker)
    consumer.setup_topology()

    # --- Step 1: Create Diverse Passenger Profiles ---
    line_id = "line-1"
    stop_id = "stop-101"
    trip_id = "trip-201"
    unrelated_line = "line-99"

    # Passenger A: Subscribed to Line 1 (both IN_APP and EMAIL)
    p_line = uuid.uuid4()
    Subscription.objects.create(passenger_id=p_line, entity_type=EntityType.LINE, entity_id=line_id, active=True)
    NotificationPreference.objects.create(
        passenger_id=p_line,
        channel=NotificationChannel.IN_APP,
        enabled=True,
        enabled_change_types=[ChangeType.DISRUPTION],
    )
    NotificationPreference.objects.create(
        passenger_id=p_line,
        channel=NotificationChannel.EMAIL,
        enabled=True,
        enabled_change_types=[ChangeType.DISRUPTION],
    )

    # Passenger B: Subscribed to Stop 101 (only IN_APP enabled, EMAIL disabled)
    p_stop = uuid.uuid4()
    Subscription.objects.create(passenger_id=p_stop, entity_type=EntityType.STOP, entity_id=stop_id, active=True)
    NotificationPreference.objects.create(
        passenger_id=p_stop,
        channel=NotificationChannel.IN_APP,
        enabled=True,
        enabled_change_types=[ChangeType.DISRUPTION],
    )
    NotificationPreference.objects.create(
        passenger_id=p_stop,
        channel=NotificationChannel.EMAIL,
        enabled=False,
        enabled_change_types=[ChangeType.DISRUPTION],
    )

    # Passenger C: Subscribed to Trip 201 (both channels enabled)
    p_trip = uuid.uuid4()
    Subscription.objects.create(passenger_id=p_trip, entity_type=EntityType.TRIP, entity_id=trip_id, active=True)
    NotificationPreference.objects.create(
        passenger_id=p_trip,
        channel=NotificationChannel.IN_APP,
        enabled=True,
        enabled_change_types=[ChangeType.DISRUPTION],
    )
    NotificationPreference.objects.create(
        passenger_id=p_trip,
        channel=NotificationChannel.EMAIL,
        enabled=True,
        enabled_change_types=[ChangeType.DISRUPTION],
    )

    # Passenger D (Overlapping): Subscribed to BOTH Line 1 AND Stop 101 (FR-065)
    p_overlap = uuid.uuid4()
    Subscription.objects.create(passenger_id=p_overlap, entity_type=EntityType.LINE, entity_id=line_id, active=True)
    Subscription.objects.create(passenger_id=p_overlap, entity_type=EntityType.STOP, entity_id=stop_id, active=True)
    NotificationPreference.objects.create(
        passenger_id=p_overlap,
        channel=NotificationChannel.IN_APP,
        enabled=True,
        enabled_change_types=[ChangeType.DISRUPTION],
    )
    NotificationPreference.objects.create(
        passenger_id=p_overlap,
        channel=NotificationChannel.EMAIL,
        enabled=True,
        enabled_change_types=[ChangeType.DISRUPTION],
    )

    # Passenger E (Unrelated line): Subscribed only to Line 99
    p_unrelated = uuid.uuid4()
    Subscription.objects.create(
        passenger_id=p_unrelated, entity_type=EntityType.LINE, entity_id=unrelated_line, active=True
    )

    # Passenger F (Disabled preference): Subscribed to Line 1, but preferences disabled
    p_optout = uuid.uuid4()
    Subscription.objects.create(passenger_id=p_optout, entity_type=EntityType.LINE, entity_id=line_id, active=True)
    NotificationPreference.objects.create(
        passenger_id=p_optout,
        channel=NotificationChannel.IN_APP,
        enabled=False,
        enabled_change_types=[ChangeType.DISRUPTION],
    )
    NotificationPreference.objects.create(
        passenger_id=p_optout,
        channel=NotificationChannel.EMAIL,
        enabled=False,
        enabled_change_types=[ChangeType.DISRUPTION],
    )

    # --- Step 2: Lifecycle Event 1 — Disruption Registered (DisruptionReported) ---
    ev1_id = uuid.uuid4()
    ev1 = _make_envelope(
        event_id=ev1_id,
        event_type="DisruptionReported",
        payload={
            "changeType": ChangeType.DISRUPTION,
            "entityType": EntityType.LINE,
            "entityId": line_id,
            "lineId": line_id,
            "stopIds": [stop_id],
            "relatedEntities": [("TRIP", trip_id)],
            "title": "Line 1 Track Obstruction",
            "description": "Tree fallen on tracks between Stop 100 and Stop 101.",
        },
    )
    broker.publish(ev1)
    consumer.consume_batch(max_messages=10)

    # Assert Passenger A (Line sub): Received 1 IN_APP + 1 EMAIL
    assert list_passenger_notifications(p_line).count() == 1
    assert NotificationRecord.objects.filter(event_id=ev1_id, passenger_id=p_line).count() == 2

    # Assert Passenger B (Stop sub): Received 1 IN_APP only (EMAIL disabled by preference)
    assert list_passenger_notifications(p_stop).count() == 1
    p_stop_records = NotificationRecord.objects.filter(event_id=ev1_id, passenger_id=p_stop)
    assert p_stop_records.count() == 1
    assert p_stop_records.first().channel == NotificationChannel.IN_APP

    # Assert Passenger C (Trip sub): Received 1 IN_APP + 1 EMAIL
    assert list_passenger_notifications(p_trip).count() == 1
    assert NotificationRecord.objects.filter(event_id=ev1_id, passenger_id=p_trip).count() == 2

    # Assert Passenger D (Overlapping): Exactly 1 IN_APP + 1 EMAIL (no duplicate for overlapping match - FR-065)
    assert list_passenger_notifications(p_overlap).count() == 1
    assert NotificationRecord.objects.filter(event_id=ev1_id, passenger_id=p_overlap).count() == 2

    # Assert Passenger E & F (Unrelated & Opted-out): Received 0
    assert list_passenger_notifications(p_unrelated).count() == 0
    assert list_passenger_notifications(p_optout).count() == 0

    # --- Step 3: Lifecycle Event 2 — Disruption Updated (DisruptionUpdated) ---
    ev2_id = uuid.uuid4()
    ev2 = _make_envelope(
        event_id=ev2_id,
        event_type="DisruptionUpdated",
        payload={
            "changeType": ChangeType.DISRUPTION,
            "entityType": EntityType.LINE,
            "entityId": line_id,
            "lineId": line_id,
            "stopIds": [stop_id],
            "relatedEntities": [("TRIP", trip_id)],
            "title": "Line 1 Delay Extended to 45m",
            "description": "Removal crew on site; clearing underway.",
        },
    )
    broker.publish(ev2)
    consumer.consume_batch(max_messages=10)

    # Inboxes now contain 2 history entries
    assert list_passenger_notifications(p_line).count() == 2
    assert list_passenger_notifications(p_overlap).count() == 2

    # --- Step 4: Lifecycle Event 3 — Disruption Resolved (DisruptionResolved) ---
    ev3_id = uuid.uuid4()
    ev3 = _make_envelope(
        event_id=ev3_id,
        event_type="DisruptionResolved",
        payload={
            "changeType": ChangeType.DISRUPTION,
            "entityType": EntityType.LINE,
            "entityId": line_id,
            "lineId": line_id,
            "stopIds": [stop_id],
            "relatedEntities": [("TRIP", trip_id)],
            "title": "Line 1 Service Restored",
            "description": "Tracks cleared; all trips resuming normal timetable.",
        },
    )
    broker.publish(ev3)
    consumer.consume_batch(max_messages=10)

    # Verify inbox history ordering (newest first - conventions.md, API)
    line_history = list(list_passenger_notifications(p_line))
    assert len(line_history) == 3
    assert line_history[0].event_id == ev3_id
    assert line_history[0].title == "Line 1 Service Restored"
    assert line_history[1].event_id == ev2_id
    assert line_history[1].title == "Line 1 Delay Extended to 45m"
    assert line_history[2].event_id == ev1_id
    assert line_history[2].title == "Line 1 Track Obstruction"

    # --- Step 5: Read Receipts & In-App Management (FR-067) ---
    # Mark single notification as read
    first_notif = line_history[0]
    mark_as_read(passenger_id=p_line, notification_id=first_notif.id)
    first_notif.refresh_from_db()
    assert first_notif.read_at is not None

    # Mark remaining notifications as read
    marked_count = mark_all_as_read(passenger_id=p_line)
    assert marked_count == 2
    assert list_passenger_notifications(p_line, unread_only=True).count() == 0

    # --- Step 6: Deduplication Check on Redelivery (FR-066) ---
    # Replay Event 1 (simulated network replay or broker redelivery)
    broker.publish(ev1)
    processed = consumer.consume_batch(max_messages=10)
    assert processed == 1

    # Verified: NO additional inbox entries created; count remains 3
    assert list_passenger_notifications(p_line).count() == 3
    # NotificationRecord count per passenger remains unchanged
    assert NotificationRecord.objects.filter(event_id=ev1_id, passenger_id=p_line).count() == 2


@pytest.mark.django_db
@pytest.mark.req("E2E-05", "FR-068")
def test_e2e_event_time_temporal_preference_matching() -> None:
    """E2E-05 / FR-068: Validate that subscriptions and preferences valid at event occurred_at

    are strictly respected, even if modified after the event.
    """
    broker = MockAmqpBroker()
    consumer = NotificationEventConsumer(channel=broker)

    t0 = datetime.now(UTC) - timedelta(minutes=10)
    t_after = datetime.now(UTC)

    # Passenger 1: Subscribed BEFORE event, cancelled AFTER event
    p_cancelled = uuid.uuid4()
    sub_1 = Subscription.objects.create(
        passenger_id=p_cancelled,
        entity_type=EntityType.LINE,
        entity_id="line-temporal",
        active=True,
    )
    # Backdate creation
    Subscription.objects.filter(id=sub_1.id).update(created_at=t0 - timedelta(minutes=5))
    # Cancel after event
    sub_1.active = False
    sub_1.cancelled_at = t_after
    sub_1.save(update_fields=["active", "cancelled_at"])

    # Passenger 2: Subscribed AFTER event occurred
    p_new = uuid.uuid4()
    sub_2 = Subscription.objects.create(
        passenger_id=p_new,
        entity_type=EntityType.LINE,
        entity_id="line-temporal",
        active=True,
    )
    Subscription.objects.filter(id=sub_2.id).update(created_at=t_after)

    # Event occurred at t0 (when Passenger 1 was active and Passenger 2 did not exist)
    ev_id = uuid.uuid4()
    ev = _make_envelope(
        event_id=ev_id,
        event_type="DisruptionReported",
        payload={
            "changeType": ChangeType.DISRUPTION,
            "entityType": EntityType.LINE,
            "entityId": "line-temporal",
            "title": "Temporal Test Disruption",
            "description": "Event occurred at t0.",
        },
        occurred_at=t0,
    )

    broker.publish(ev)
    consumer.consume_batch(max_messages=10)

    # Passenger 1 WAS active at event occurred_at -> receives notification
    assert list_passenger_notifications(p_cancelled).count() == 1
    # Passenger 2 subscribed AFTER event occurred_at -> receives 0 notifications
    assert list_passenger_notifications(p_new).count() == 0
