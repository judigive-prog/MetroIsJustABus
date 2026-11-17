import datetime
import uuid

import pytest

from inbox.models import InboxNotification
from notifications.models import DeliveryStatus, NotificationRecord
from notifications.services import RelevantChangeEvent, process_relevant_change
from preferences.models import ChangeType, NotificationChannel
from preferences.services import set_preference
from subscriptions.models import EntityType, Subscription
from subscriptions.services import cancel_subscription


@pytest.mark.django_db
@pytest.mark.req("FR-068")
def test_subscription_active_at_event_time_matches_even_if_cancelled_later() -> None:
    """Passenger subscribed at event time but cancelled before processing time still receives notification (FR-068)."""
    passenger_id = uuid.uuid4()
    base_time = datetime.datetime(2026, 11, 1, 10, 0, tzinfo=datetime.UTC)
    event_time = base_time + datetime.timedelta(minutes=15)  # 10:15
    cancel_time = base_time + datetime.timedelta(minutes=30)  # 10:30

    # Subscription created at 10:00
    sub = Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-yellow",
        active=True,
    )
    # Manually backdate created_at to simulate creation before event
    Subscription.objects.filter(id=sub.id).update(created_at=base_time)

    # Subscription cancelled at 10:30 (after the event happened)
    cancel_subscription(subscription_id=sub.id, passenger_id=passenger_id)
    Subscription.objects.filter(id=sub.id).update(cancelled_at=cancel_time, active=False)

    event_id = uuid.uuid4()
    event = RelevantChangeEvent(
        event_id=event_id,
        change_type=ChangeType.DISRUPTION,
        entity_type=EntityType.LINE,
        entity_id="line-yellow",
        title="Yellow Line Incident",
        body="Service disrupted at 10:15",
        occurred_at=event_time,
    )

    # Process event at 11:00 (delayed processing)
    records = process_relevant_change(event)
    assert len(records) == 2
    assert InboxNotification.objects.filter(passenger_id=passenger_id, event_id=event_id).count() == 1
    for rec in records:
        assert rec.status == DeliveryStatus.DELIVERED


@pytest.mark.django_db
@pytest.mark.req("FR-068")
def test_subscription_created_after_event_time_is_excluded() -> None:
    """Subscription created after event time does not match event (FR-068)."""
    passenger_id = uuid.uuid4()
    event_time = datetime.datetime(2026, 11, 1, 10, 0, tzinfo=datetime.UTC)
    subscribe_time = event_time + datetime.timedelta(minutes=30)  # 10:30

    # Passenger subscribes at 10:30
    sub = Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-yellow",
        active=True,
    )
    Subscription.objects.filter(id=sub.id).update(created_at=subscribe_time)

    event_id = uuid.uuid4()
    event = RelevantChangeEvent(
        event_id=event_id,
        change_type=ChangeType.DISRUPTION,
        entity_type=EntityType.LINE,
        entity_id="line-yellow",
        title="Past Incident",
        body="Disruption at 10:00",
        occurred_at=event_time,
    )

    records = process_relevant_change(event)
    assert len(records) == 0
    assert InboxNotification.objects.filter(passenger_id=passenger_id, event_id=event_id).count() == 0


@pytest.mark.django_db
@pytest.mark.req("FR-068")
def test_subscription_cancelled_before_event_time_is_excluded() -> None:
    """Subscription cancelled before the event occurred does not match (FR-068)."""
    passenger_id = uuid.uuid4()
    create_time = datetime.datetime(2026, 11, 1, 9, 0, tzinfo=datetime.UTC)
    cancel_time = datetime.datetime(2026, 11, 1, 9, 30, tzinfo=datetime.UTC)
    event_time = datetime.datetime(2026, 11, 1, 10, 0, tzinfo=datetime.UTC)

    sub = Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-yellow",
        active=False,
    )
    Subscription.objects.filter(id=sub.id).update(created_at=create_time, cancelled_at=cancel_time)

    event = RelevantChangeEvent(
        event_id=uuid.uuid4(),
        change_type=ChangeType.DISRUPTION,
        entity_type=EntityType.LINE,
        entity_id="line-yellow",
        title="Incident",
        body="Service disrupted at 10:00",
        occurred_at=event_time,
    )

    records = process_relevant_change(event)
    assert len(records) == 0


@pytest.mark.django_db
@pytest.mark.req("FR-068")
def test_preference_state_valid_at_event_time_respected_after_later_change() -> None:
    """Verifies that preferences active at event time are used rather than processing-time state (FR-068)."""
    passenger_id = uuid.uuid4()
    t_pref_1 = datetime.datetime(2026, 11, 1, 9, 0, tzinfo=datetime.UTC)
    t_event = datetime.datetime(2026, 11, 1, 10, 0, tzinfo=datetime.UTC)
    t_pref_2 = datetime.datetime(2026, 11, 1, 10, 30, tzinfo=datetime.UTC)

    # Active subscription
    sub = Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-red",
        active=True,
    )
    Subscription.objects.filter(id=sub.id).update(created_at=t_pref_1)

    # Preference 1 at 09:00: EMAIL is ENABLED
    set_preference(
        passenger_id=passenger_id,
        channel=NotificationChannel.EMAIL,
        enabled=True,
        enabled_change_types=[ChangeType.DISRUPTION],
    )
    from preferences.models import PreferenceHistory

    PreferenceHistory.objects.filter(passenger_id=passenger_id, channel=NotificationChannel.EMAIL).update(
        valid_from=t_pref_1, valid_to=t_pref_2
    )

    # Preference 2 at 10:30: Passenger DISABLES EMAIL
    set_preference(
        passenger_id=passenger_id,
        channel=NotificationChannel.EMAIL,
        enabled=False,
        enabled_change_types=[],
    )
    PreferenceHistory.objects.filter(
        passenger_id=passenger_id,
        channel=NotificationChannel.EMAIL,
        valid_to__isnull=True,
    ).update(valid_from=t_pref_2)

    # Event occurred at 10:00 (when EMAIL was still ENABLED)
    event_id = uuid.uuid4()
    event = RelevantChangeEvent(
        event_id=event_id,
        change_type=ChangeType.DISRUPTION,
        entity_type=EntityType.LINE,
        entity_id="line-red",
        title="Red Line Delay",
        body="Red line disrupted at 10:00",
        occurred_at=t_event,
    )

    # Delayed processing occurs at 11:00
    records = process_relevant_change(event)

    # Passenger should receive EMAIL because EMAIL was ENABLED at 10:00!
    email_records = [r for r in records if r.channel == NotificationChannel.EMAIL]
    assert len(email_records) == 1
    assert email_records[0].status == DeliveryStatus.DELIVERED


@pytest.mark.django_db
@pytest.mark.req("FR-068")
def test_preference_disabled_at_event_time_respected_even_if_enabled_later() -> None:
    """Passenger who enabled notifications after the event does not receive event notification retroactively (FR-068)."""
    passenger_id = uuid.uuid4()
    t_pref_1 = datetime.datetime(2026, 11, 1, 9, 0, tzinfo=datetime.UTC)
    t_event = datetime.datetime(2026, 11, 1, 10, 0, tzinfo=datetime.UTC)
    t_pref_2 = datetime.datetime(2026, 11, 1, 10, 30, tzinfo=datetime.UTC)

    sub = Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-blue",
        active=True,
    )
    Subscription.objects.filter(id=sub.id).update(created_at=t_pref_1)

    # Preference 1 at 09:00: EMAIL is DISABLED
    set_preference(
        passenger_id=passenger_id,
        channel=NotificationChannel.EMAIL,
        enabled=False,
        enabled_change_types=[],
    )
    from preferences.models import PreferenceHistory

    PreferenceHistory.objects.filter(passenger_id=passenger_id, channel=NotificationChannel.EMAIL).update(
        valid_from=t_pref_1, valid_to=t_pref_2
    )

    # Preference 2 at 10:30: Passenger ENABLES EMAIL
    set_preference(
        passenger_id=passenger_id,
        channel=NotificationChannel.EMAIL,
        enabled=True,
        enabled_change_types=[ChangeType.DISRUPTION],
    )
    PreferenceHistory.objects.filter(
        passenger_id=passenger_id,
        channel=NotificationChannel.EMAIL,
        valid_to__isnull=True,
    ).update(valid_from=t_pref_2)

    # Event occurred at 10:00 (when EMAIL was DISABLED)
    event_id = uuid.uuid4()
    event = RelevantChangeEvent(
        event_id=event_id,
        change_type=ChangeType.DISRUPTION,
        entity_type=EntityType.LINE,
        entity_id="line-blue",
        title="Blue Line Alert",
        body="Event occurred at 10:00",
        occurred_at=t_event,
    )

    records = process_relevant_change(event)

    # EMAIL record must NOT exist because EMAIL was disabled at event time
    email_records = [r for r in records if r.channel == NotificationChannel.EMAIL]
    assert len(email_records) == 0
    assert NotificationRecord.objects.filter(event_id=event_id, channel=NotificationChannel.EMAIL).count() == 0
