import uuid
from unittest.mock import MagicMock

import pytest

from inbox.models import InboxNotification
from notifications.models import DeliveryStatus, NotificationRecord
from notifications.selectors import (
    get_notification_records_for_event,
    is_notification_delivered,
    list_delivered_passengers_for_event,
)
from notifications.services import RelevantChangeEvent, process_relevant_change
from preferences.models import ChangeType, NotificationChannel
from subscriptions.models import EntityType, Subscription


@pytest.mark.django_db
@pytest.mark.req("FR-066")
def test_redelivery_does_not_send_duplicate_notifications() -> None:
    """Verifies that redelivery of an event does not send duplicate notifications (FR-066)."""
    passenger_id = uuid.uuid4()
    event_id = uuid.uuid4()

    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-green",
        active=True,
    )

    event = RelevantChangeEvent(
        event_id=event_id,
        change_type=ChangeType.DISRUPTION,
        entity_type=EntityType.LINE,
        entity_id="line-green",
        title="Green Line Maintenance",
        body="Track repairs scheduled.",
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

    dispatchers = {
        NotificationChannel.IN_APP: mock_in_app,
        NotificationChannel.EMAIL: mock_email,
    }

    # First delivery
    records_first = process_relevant_change(event, dispatchers=dispatchers)
    assert len(records_first) == 2
    assert mock_in_app.call_count == 1
    assert mock_email.call_count == 1

    inbox_items = InboxNotification.objects.filter(passenger_id=passenger_id, event_id=event_id)
    assert inbox_items.count() == 1

    for r in records_first:
        assert r.status == DeliveryStatus.DELIVERED
        assert r.attempts == 1

    # Second delivery (Event redelivery)
    records_second = process_relevant_change(event, dispatchers=dispatchers)
    assert len(records_second) == 2
    # Mock dispatchers MUST NOT be invoked a second time
    assert mock_in_app.call_count == 1
    assert mock_email.call_count == 1

    # Database records must remain exactly 1 per channel and 1 inbox item
    assert InboxNotification.objects.filter(passenger_id=passenger_id, event_id=event_id).count() == 1
    records_in_db = get_notification_records_for_event(event_id)
    assert records_in_db.count() == 2
    for r in records_in_db:
        assert r.status == DeliveryStatus.DELIVERED
        assert r.attempts == 1

    assert is_notification_delivered(event_id, passenger_id, NotificationChannel.IN_APP) is True
    assert is_notification_delivered(event_id, passenger_id, NotificationChannel.EMAIL) is True


@pytest.mark.django_db
@pytest.mark.req("FR-066")
def test_redelivery_after_simulated_channel_response_failure() -> None:
    """Verifies logical deduplication boundary when an event is redelivered after simulated failure (FR-066)."""
    passenger_id = uuid.uuid4()
    event_id = uuid.uuid4()

    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.STOP,
        entity_id="stop-north",
        active=True,
    )

    event = RelevantChangeEvent(
        event_id=event_id,
        change_type=ChangeType.DELAY,
        entity_type=EntityType.STOP,
        entity_id="stop-north",
        title="North Stop Delay",
        body="Trains delayed by 10 minutes.",
    )

    in_app_calls = 0
    email_calls = 0
    fail_email = True

    def mock_in_app(ev: RelevantChangeEvent, p_id: uuid.UUID) -> None:
        nonlocal in_app_calls
        in_app_calls += 1
        InboxNotification.objects.create(
            passenger_id=p_id,
            event_id=ev.event_id,
            title=ev.title,
            body=ev.body,
            change_type=ev.change_type,
            entity_type=ev.entity_type,
            entity_id=ev.entity_id,
        )

    def mock_email(ev: RelevantChangeEvent, p_id: uuid.UUID) -> None:
        nonlocal email_calls
        email_calls += 1
        if fail_email:
            raise ConnectionResetError("Simulated SMTP network response failure")

    dispatchers = {
        NotificationChannel.IN_APP: mock_in_app,
        NotificationChannel.EMAIL: mock_email,
    }

    # Attempt 1: In-App succeeds, Email experiences response failure
    records_1 = process_relevant_change(event, dispatchers=dispatchers, raise_on_failure=False)
    assert len(records_1) == 2
    assert in_app_calls == 1
    assert email_calls == 1

    in_app_rec = NotificationRecord.objects.get(event_id=event_id, channel=NotificationChannel.IN_APP)
    assert in_app_rec.status == DeliveryStatus.DELIVERED
    assert in_app_rec.attempts == 1

    email_rec = NotificationRecord.objects.get(event_id=event_id, channel=NotificationChannel.EMAIL)
    assert email_rec.status == DeliveryStatus.FAILED
    assert email_rec.attempts == 1
    assert "Simulated SMTP network response failure" in email_rec.error_message

    assert is_notification_delivered(event_id, passenger_id, NotificationChannel.IN_APP) is True
    assert is_notification_delivered(event_id, passenger_id, NotificationChannel.EMAIL) is False

    # Attempt 2: Event is redelivered / retried after email service recovered
    fail_email = False
    records_2 = process_relevant_change(event, dispatchers=dispatchers, raise_on_failure=False)
    assert len(records_2) == 2

    # In-App was ALREADY delivered -> Logical deduplication boundary skips it!
    assert in_app_calls == 1
    # Email was FAILED -> Retried and now called a second time
    assert email_calls == 2

    # Verify updated database state
    in_app_rec.refresh_from_db()
    assert in_app_rec.status == DeliveryStatus.DELIVERED
    assert in_app_rec.attempts == 1

    email_rec.refresh_from_db()
    assert email_rec.status == DeliveryStatus.DELIVERED
    assert email_rec.attempts == 2
    assert email_rec.error_message == ""

    assert InboxNotification.objects.filter(passenger_id=passenger_id, event_id=event_id).count() == 1
    assert is_notification_delivered(event_id, passenger_id, NotificationChannel.EMAIL) is True
    assert list_delivered_passengers_for_event(event_id) == {passenger_id}


@pytest.mark.django_db
@pytest.mark.req("FR-066")
def test_redelivery_after_hard_exception_with_raise_on_failure() -> None:
    """Verifies that when a hard exception is raised, partial progress is saved and deduplicated on retry (FR-066)."""
    passenger_id = uuid.uuid4()
    event_id = uuid.uuid4()

    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-yellow",
        active=True,
    )

    event = RelevantChangeEvent(
        event_id=event_id,
        change_type=ChangeType.DISRUPTION,
        entity_type=EntityType.LINE,
        entity_id="line-yellow",
        title="Yellow Line Down",
        body="Power outage.",
    )

    fail_email = True
    in_app_calls = 0

    def mock_in_app(ev: RelevantChangeEvent, p_id: uuid.UUID) -> None:
        nonlocal in_app_calls
        in_app_calls += 1
        InboxNotification.objects.create(
            passenger_id=p_id,
            event_id=ev.event_id,
            title=ev.title,
            body=ev.body,
            change_type=ev.change_type,
            entity_type=ev.entity_type,
            entity_id=ev.entity_id,
        )

    def mock_email(ev: RelevantChangeEvent, p_id: uuid.UUID) -> None:
        if fail_email:
            raise RuntimeError("Downstream service crashed")

    dispatchers = {
        NotificationChannel.IN_APP: mock_in_app,
        NotificationChannel.EMAIL: mock_email,
    }

    # Attempt 1: raise_on_failure=True raises the exception
    with pytest.raises(RuntimeError, match="Downstream service crashed"):
        process_relevant_change(event, dispatchers=dispatchers, raise_on_failure=True)

    assert in_app_calls == 1
    # Check that in_app delivery was committed and email failure recorded
    in_app_rec = NotificationRecord.objects.get(event_id=event_id, channel=NotificationChannel.IN_APP)
    assert in_app_rec.status == DeliveryStatus.DELIVERED
    assert InboxNotification.objects.filter(passenger_id=passenger_id, event_id=event_id).count() == 1

    email_rec = NotificationRecord.objects.get(event_id=event_id, channel=NotificationChannel.EMAIL)
    assert email_rec.status == DeliveryStatus.FAILED
    assert email_rec.attempts == 1

    # Attempt 2: retry with healthy service
    fail_email = False
    process_relevant_change(event, dispatchers=dispatchers, raise_on_failure=True)

    # In-app was NOT called again
    assert in_app_calls == 1
    assert InboxNotification.objects.filter(passenger_id=passenger_id, event_id=event_id).count() == 1

    email_rec.refresh_from_db()
    assert email_rec.status == DeliveryStatus.DELIVERED
    assert email_rec.attempts == 2


@pytest.mark.django_db
@pytest.mark.req("FR-066")
def test_multi_passenger_deduplication_and_partial_retry() -> None:
    """Verifies deduplication boundaries across multiple passengers during redelivery (FR-066)."""
    p1 = uuid.uuid4()
    p2 = uuid.uuid4()
    event_id = uuid.uuid4()

    for p in (p1, p2):
        Subscription.objects.create(
            passenger_id=p,
            entity_type=EntityType.LINE,
            entity_id="line-blue",
            active=True,
        )

    event = RelevantChangeEvent(
        event_id=event_id,
        change_type=ChangeType.SCHEDULE_CHANGE,
        entity_type=EntityType.LINE,
        entity_id="line-blue",
        title="Schedule Adjusted",
        body="New timetable active.",
    )

    failed_passengers = {p2}

    def failing_email_dispatcher(ev: RelevantChangeEvent, p_id: uuid.UUID) -> None:
        if p_id in failed_passengers:
            raise ValueError(f"Temporary delivery failure for passenger {p_id}")

    dispatchers = {
        NotificationChannel.EMAIL: failing_email_dispatcher,
    }

    # Attempt 1: P1 succeeds for both channels, P2 fails on EMAIL
    records_1 = process_relevant_change(event, dispatchers=dispatchers)
    assert len(records_1) == 4

    # Both got in-app
    assert InboxNotification.objects.filter(event_id=event_id).count() == 2

    # P1 is fully delivered
    assert (
        NotificationRecord.objects.get(event_id=event_id, passenger_id=p1, channel=NotificationChannel.IN_APP).status
        == DeliveryStatus.DELIVERED
    )
    assert (
        NotificationRecord.objects.get(event_id=event_id, passenger_id=p1, channel=NotificationChannel.EMAIL).status
        == DeliveryStatus.DELIVERED
    )

    # P2 has EMAIL failed
    assert (
        NotificationRecord.objects.get(event_id=event_id, passenger_id=p2, channel=NotificationChannel.EMAIL).status
        == DeliveryStatus.FAILED
    )

    # Attempt 2: P2 failure resolved, redeliver event
    failed_passengers.clear()
    records_2 = process_relevant_change(event, dispatchers=dispatchers)
    assert len(records_2) == 4

    # No duplicate inbox items created
    assert InboxNotification.objects.filter(event_id=event_id).count() == 2

    # Now all records delivered
    for rec in NotificationRecord.objects.filter(event_id=event_id):
        assert rec.status == DeliveryStatus.DELIVERED
