import uuid

import pytest

from inbox.models import InboxNotification
from notifications.models import DeliveryStatus, NotificationRecord
from notifications.selectors import (
    get_notification_records_for_event,
    get_notification_records_for_passenger,
    list_delivered_passengers_for_event,
)
from notifications.services import RelevantChangeEvent, process_relevant_change
from preferences.models import ChangeType, NotificationChannel, NotificationPreference
from subscriptions.models import EntityType, Subscription


@pytest.mark.django_db
@pytest.mark.req("FR-063")
def test_affected_passenger_receives_notifications() -> None:
    passenger_id = uuid.uuid4()
    event_id = uuid.uuid4()

    # Create active subscription for passenger
    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-blue",
        active=True,
    )

    event = RelevantChangeEvent(
        event_id=event_id,
        change_type=ChangeType.DISRUPTION,
        entity_type=EntityType.LINE,
        entity_id="line-blue",
        title="Blue Line Disruption",
        body="Major delay due to track maintenance.",
    )

    records = process_relevant_change(event)
    assert len(records) == 2  # IN_APP and EMAIL by default

    # Verify InboxNotification created
    inbox_items = InboxNotification.objects.filter(passenger_id=passenger_id, event_id=event_id)
    assert inbox_items.count() == 1
    inbox_item = inbox_items.first()
    assert inbox_item.title == "Blue Line Disruption"
    assert inbox_item.change_type == ChangeType.DISRUPTION
    assert inbox_item.entity_type == EntityType.LINE
    assert inbox_item.entity_id == "line-blue"
    assert inbox_item.read_at is None

    # Verify Delivery Records
    channels = {r.channel for r in records}
    assert channels == {NotificationChannel.IN_APP, NotificationChannel.EMAIL}
    for r in records:
        assert r.status == DeliveryStatus.DELIVERED
        assert r.passenger_id == passenger_id
        assert r.event_id == event_id

    # Verify selectors
    delivered = list_delivered_passengers_for_event(event_id)
    assert delivered == {passenger_id}

    event_records = get_notification_records_for_event(event_id)
    assert event_records.count() == 2

    passenger_records = get_notification_records_for_passenger(passenger_id)
    assert passenger_records.count() == 2


@pytest.mark.django_db
@pytest.mark.req("FR-063", "FR-102")
def test_unrelated_passengers_excluded() -> None:
    passenger_affected = uuid.uuid4()
    passenger_other_line = uuid.uuid4()
    passenger_unsubscribed = uuid.uuid4()
    event_id = uuid.uuid4()

    Subscription.objects.create(
        passenger_id=passenger_affected,
        entity_type=EntityType.LINE,
        entity_id="line-red",
        active=True,
    )
    Subscription.objects.create(
        passenger_id=passenger_other_line,
        entity_type=EntityType.LINE,
        entity_id="line-green",
        active=True,
    )

    event = RelevantChangeEvent(
        event_id=event_id,
        change_type=ChangeType.DISRUPTION,
        entity_type=EntityType.LINE,
        entity_id="line-red",
        title="Red Line Maintenance",
        body="Red Line is disrupted.",
    )

    process_relevant_change(event)

    # Affected passenger got notification
    assert InboxNotification.objects.filter(passenger_id=passenger_affected).count() == 1
    assert NotificationRecord.objects.filter(passenger_id=passenger_affected).count() == 2

    # Unrelated passengers got nothing
    assert InboxNotification.objects.filter(passenger_id=passenger_other_line).count() == 0
    assert NotificationRecord.objects.filter(passenger_id=passenger_other_line).count() == 0

    assert InboxNotification.objects.filter(passenger_id=passenger_unsubscribed).count() == 0
    assert NotificationRecord.objects.filter(passenger_id=passenger_unsubscribed).count() == 0

    delivered = list_delivered_passengers_for_event(event_id)
    assert delivered == {passenger_affected}


@pytest.mark.django_db
@pytest.mark.req("FR-063", "FR-062")
def test_channel_preferences_respected() -> None:
    passenger_id = uuid.uuid4()
    event_id = uuid.uuid4()

    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.STOP,
        entity_id="stop-central",
        active=True,
    )

    # Disable EMAIL channel for passenger
    NotificationPreference.objects.create(
        passenger_id=passenger_id,
        channel=NotificationChannel.EMAIL,
        enabled=False,
        enabled_change_types=[ChangeType.DISRUPTION],
    )

    event = RelevantChangeEvent(
        event_id=event_id,
        change_type=ChangeType.DISRUPTION,
        entity_type=EntityType.STOP,
        entity_id="stop-central",
        title="Central Stop Closed",
        body="Elevator maintenance at Central.",
    )

    records = process_relevant_change(event)
    assert len(records) == 1
    assert records[0].channel == NotificationChannel.IN_APP

    # In-app exists, email record does not exist
    assert InboxNotification.objects.filter(passenger_id=passenger_id, event_id=event_id).count() == 1
    assert (
        NotificationRecord.objects.filter(
            passenger_id=passenger_id,
            channel=NotificationChannel.EMAIL,
        ).count()
        == 0
    )


@pytest.mark.django_db
@pytest.mark.req("FR-063", "FR-062")
def test_change_type_preference_skips_unwanted_notifications() -> None:
    passenger_id = uuid.uuid4()
    event_id = uuid.uuid4()

    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.TRIP,
        entity_id="trip-101",
        active=True,
    )

    # Only enable DISRUPTION, not DELAY
    NotificationPreference.objects.create(
        passenger_id=passenger_id,
        channel=NotificationChannel.IN_APP,
        enabled=True,
        enabled_change_types=[ChangeType.DISRUPTION],
    )
    NotificationPreference.objects.create(
        passenger_id=passenger_id,
        channel=NotificationChannel.EMAIL,
        enabled=True,
        enabled_change_types=[ChangeType.DISRUPTION],
    )

    event = RelevantChangeEvent(
        event_id=event_id,
        change_type=ChangeType.DELAY,
        entity_type=EntityType.TRIP,
        entity_id="trip-101",
        title="Trip Delayed",
        body="Trip 101 delayed by 15 mins.",
    )

    records = process_relevant_change(event)
    assert len(records) == 0
    assert InboxNotification.objects.filter(passenger_id=passenger_id).count() == 0
    assert NotificationRecord.objects.filter(passenger_id=passenger_id).count() == 0


@pytest.mark.django_db
@pytest.mark.req("FR-063", "FR-061")
def test_inactive_subscription_excluded() -> None:
    passenger_id = uuid.uuid4()
    event_id = uuid.uuid4()

    # Cancelled / inactive subscription
    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-yellow",
        active=False,
    )

    event = RelevantChangeEvent(
        event_id=event_id,
        change_type=ChangeType.DISRUPTION,
        entity_type=EntityType.LINE,
        entity_id="line-yellow",
        title="Yellow Line Incident",
        body="Service suspended.",
    )

    records = process_relevant_change(event)
    assert len(records) == 0
    assert InboxNotification.objects.filter(passenger_id=passenger_id).count() == 0
    assert NotificationRecord.objects.filter(passenger_id=passenger_id).count() == 0
