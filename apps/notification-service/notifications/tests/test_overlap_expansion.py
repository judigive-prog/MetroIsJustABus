import uuid
from unittest.mock import MagicMock

import pytest

from inbox.models import InboxNotification
from notifications.models import DeliveryStatus
from notifications.selectors import (
    get_notification_records_for_passenger,
    list_delivered_passengers_for_event,
)
from notifications.services import (
    RelevantChangeEvent,
    expand_affected_entities,
    process_relevant_change,
)
from preferences.models import ChangeType, NotificationChannel
from subscriptions.models import EntityType, Subscription


@pytest.mark.req("FR-065")
def test_expand_affected_entities_rules() -> None:
    """Verifies the entity expansion hierarchy logic (FR-065)."""
    event = RelevantChangeEvent(
        event_id=uuid.uuid4(),
        change_type=ChangeType.DELAY,
        entity_type=EntityType.TRIP,
        entity_id="trip-101",
        title="Trip 101 Delay",
        body="Delayed by 10 minutes",
        line_id="line-blue",
        stop_ids=["stop-a", "stop-b"],
        related_entities=[(EntityType.STOP, "stop-c")],
    )

    expanded = expand_affected_entities(event)
    assert (EntityType.TRIP, "trip-101") in expanded
    assert (EntityType.LINE, "line-blue") in expanded
    assert (EntityType.STOP, "stop-a") in expanded
    assert (EntityType.STOP, "stop-b") in expanded
    assert (EntityType.STOP, "stop-c") in expanded


@pytest.mark.django_db
@pytest.mark.req("FR-065")
def test_line_subscription_covers_stops_and_trips() -> None:
    """Verifies that line subscriptions cover events on stops and trips belonging to that line (FR-065)."""
    passenger_id = uuid.uuid4()
    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-red",
        active=True,
    )

    # 1. Stop event on that line
    stop_event_id = uuid.uuid4()
    stop_event = RelevantChangeEvent(
        event_id=stop_event_id,
        change_type=ChangeType.DISRUPTION,
        entity_type=EntityType.STOP,
        entity_id="stop-marques",
        title="Stop Maintenance",
        body="Platform closed",
        line_id="line-red",
    )

    records = process_relevant_change(stop_event)
    assert len(records) == 2
    assert InboxNotification.objects.filter(passenger_id=passenger_id, event_id=stop_event_id).count() == 1

    # 2. Trip event on that line
    trip_event_id = uuid.uuid4()
    trip_event = RelevantChangeEvent(
        event_id=trip_event_id,
        change_type=ChangeType.DELAY,
        entity_type=EntityType.TRIP,
        entity_id="trip-red-5",
        title="Trip Delayed",
        body="5 min delay",
        line_id="line-red",
    )

    records_trip = process_relevant_change(trip_event)
    assert len(records_trip) == 2
    assert InboxNotification.objects.filter(passenger_id=passenger_id, event_id=trip_event_id).count() == 1


@pytest.mark.django_db
@pytest.mark.req("FR-065")
def test_stop_subscription_covers_trips_serving_stop() -> None:
    """Verifies that stop subscriptions cover trips serving that stop (FR-065)."""
    passenger_served = uuid.uuid4()
    passenger_unrelated = uuid.uuid4()

    Subscription.objects.create(
        passenger_id=passenger_served,
        entity_type=EntityType.STOP,
        entity_id="stop-saldanha",
        active=True,
    )
    Subscription.objects.create(
        passenger_id=passenger_unrelated,
        entity_type=EntityType.STOP,
        entity_id="stop-alameda",
        active=True,
    )

    event_id = uuid.uuid4()
    event = RelevantChangeEvent(
        event_id=event_id,
        change_type=ChangeType.DELAY,
        entity_type=EntityType.TRIP,
        entity_id="trip-yellow-12",
        title="Trip Delay",
        body="Signal failure",
        stop_ids=["stop-saldanha", "stop-campo-pequeno"],
    )

    process_relevant_change(event)
    # Only passenger_served should receive notifications
    delivered = list_delivered_passengers_for_event(event_id)
    assert delivered == {passenger_served}

    assert InboxNotification.objects.filter(passenger_id=passenger_served, event_id=event_id).count() == 1
    assert InboxNotification.objects.filter(passenger_id=passenger_unrelated).count() == 0


@pytest.mark.django_db
@pytest.mark.req("FR-065")
def test_overlapping_subscriptions_produce_single_notification() -> None:
    """Verifies that overlapping line, stop, and trip subscriptions collapse into ONE notification (FR-065)."""
    passenger_id = uuid.uuid4()
    event_id = uuid.uuid4()

    # Passenger has 3 overlapping subscriptions: line, stop on line, and trip on line serving stop
    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-blue",
        active=True,
    )
    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.STOP,
        entity_id="stop-baixa",
        active=True,
    )
    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.TRIP,
        entity_id="trip-blue-42",
        active=True,
    )

    # Event on the trip, linked to line-blue and stop-baixa
    event = RelevantChangeEvent(
        event_id=event_id,
        change_type=ChangeType.DISRUPTION,
        entity_type=EntityType.TRIP,
        entity_id="trip-blue-42",
        title="Blue Line Incident",
        body="Service disruption on Trip 42 at Baixa",
        line_id="line-blue",
        stop_ids=["stop-baixa", "stop-terreiro"],
    )

    mock_email = MagicMock()
    mock_in_app = MagicMock(
        side_effect=lambda ev, p_id: InboxNotification.objects.create(
            passenger_id=p_id,
            event_id=ev.event_id,
            title=ev.title,
            body=ev.body,
            change_type=ev.change_type,
            entity_type=ev.entity_type,
            entity_id=ev.entity_id,
        )
    )

    records = process_relevant_change(
        event,
        dispatchers={
            NotificationChannel.IN_APP: mock_in_app,
            NotificationChannel.EMAIL: mock_email,
        },
    )

    # Crucial: Exactly 1 record per enabled channel (2 total: 1 IN_APP, 1 EMAIL), NOT 6
    assert len(records) == 2
    assert mock_in_app.call_count == 1
    assert mock_email.call_count == 1

    # In-app notification inbox contains exactly 1 item
    inbox_items = InboxNotification.objects.filter(passenger_id=passenger_id, event_id=event_id)
    assert inbox_items.count() == 1

    passenger_records = get_notification_records_for_passenger(passenger_id)
    assert passenger_records.count() == 2
    for rec in passenger_records:
        assert rec.status == DeliveryStatus.DELIVERED
        assert rec.attempts == 1


@pytest.mark.django_db
@pytest.mark.req("FR-065")
def test_topology_resolver_dynamic_expansion() -> None:
    """Verifies that dynamic topology resolver expands hierarchy properly (FR-065)."""
    passenger_line = uuid.uuid4()
    passenger_stop = uuid.uuid4()
    event_id = uuid.uuid4()

    Subscription.objects.create(
        passenger_id=passenger_line,
        entity_type=EntityType.LINE,
        entity_id="line-green",
        active=True,
    )
    Subscription.objects.create(
        passenger_id=passenger_stop,
        entity_type=EntityType.STOP,
        entity_id="stop-rossio",
        active=True,
    )

    # Bare trip event without pre-populated line_id / stop_ids
    event = RelevantChangeEvent(
        event_id=event_id,
        change_type=ChangeType.SCHEDULE_CHANGE,
        entity_type=EntityType.TRIP,
        entity_id="trip-green-99",
        title="Schedule Shift",
        body="Departure pushed back 5 minutes",
    )

    def dynamic_resolver(entity_type: str, entity_id: str) -> list[tuple[str, str]]:
        if entity_type == EntityType.TRIP and entity_id == "trip-green-99":
            return [(EntityType.LINE, "line-green"), (EntityType.STOP, "stop-rossio")]
        return []

    process_relevant_change(event, topology_resolver=dynamic_resolver)

    delivered = list_delivered_passengers_for_event(event_id)
    assert delivered == {passenger_line, passenger_stop}
