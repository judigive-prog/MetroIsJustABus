import datetime
import time
import uuid

import pytest
from django.core.management import call_command

from inbox.selectors import list_passenger_notifications
from notifications.benchmarks import (
    measure_event_issuance_timing,
    run_notification_latency_benchmark,
    setup_benchmark_fixtures,
)
from notifications.events.handler import handle_event_message
from notifications.models import DeliveryStatus, NotificationRecord
from preferences.models import ChangeType, NotificationChannel
from subscriptions.models import EntityType, Subscription


@pytest.mark.django_db
@pytest.mark.req("NFR-042")
def test_notification_issued_within_30s_under_nominal_load() -> None:
    """NFR-042: Notifications for an event should be issued within 30 s of the event under nominal load."""
    num_subscribers = 100
    line_id = "line-blue"
    stop_id = "stop-central"

    setup_benchmark_fixtures(num_subscribers=num_subscribers, line_id=line_id, stop_id=stop_id)

    event_id = uuid.uuid4()
    occurred_at = datetime.datetime.now(datetime.UTC)

    raw_message = {
        "eventId": str(event_id),
        "type": "DisruptionReported",
        "version": 1,
        "producer": "core-backend",
        "occurredAt": occurred_at.isoformat(),
        "correlationId": str(uuid.uuid4()),
        "payload": {
            "changeType": ChangeType.DISRUPTION,
            "entityType": EntityType.LINE,
            "entityId": line_id,
            "stopIds": [stop_id],
            "title": "Blue Line Track Failure",
            "description": "Suspension between Station A and Station B.",
        },
    }

    t0 = time.perf_counter()
    success, status, records = handle_event_message(raw_message)
    t1 = time.perf_counter()

    elapsed_seconds = t1 - t0

    # 1. Assert successful processing
    assert success is True
    assert status == "processed"

    # 2. Under nominal load (100 subscribers), notifications must be issued in < 30 seconds
    assert elapsed_seconds < 30.0, f"Elapsed time {elapsed_seconds}s exceeded 30s threshold"

    # In practice, with in-memory SQLite / indexed PostgreSQL it completes in well under 1 second
    assert elapsed_seconds < 2.0

    # 3. Assert all 100 subscribers received their notifications
    assert len(records) == num_subscribers * 2  # IN_APP and EMAIL channels
    for r in records:
        assert r.status == DeliveryStatus.DELIVERED
        assert r.event_id == event_id


@pytest.mark.django_db
@pytest.mark.req("NFR-042")
def test_event_time_to_issuance_elapsed_calculation() -> None:
    """NFR-042: Measure elapsed time from event occurrence timestamp to notification record creation."""
    num_subscribers = 50
    line_id = "line-red"
    stop_id = "stop-red-1"

    setup_benchmark_fixtures(num_subscribers=num_subscribers, line_id=line_id, stop_id=stop_id)

    event_id = uuid.uuid4()
    occurred_at = datetime.datetime.now(datetime.UTC)

    raw_message = {
        "eventId": str(event_id),
        "type": "DisruptionReported",
        "version": 1,
        "producer": "core-backend",
        "occurredAt": occurred_at.isoformat(),
        "correlationId": str(uuid.uuid4()),
        "payload": {
            "changeType": ChangeType.DISRUPTION,
            "entityType": EntityType.LINE,
            "entityId": line_id,
            "stopIds": [stop_id],
            "title": "Red Line Signal Outage",
            "description": "Expect 15 minute delays.",
        },
    }

    handle_event_message(raw_message)

    timing = measure_event_issuance_timing(event_id=event_id, occurred_at=occurred_at)

    assert timing["record_count"] == num_subscribers * 2
    assert timing["all_within_30s"] is True
    # Max delay should be well below 30,000 ms (typically < 1000 ms)
    assert timing["max_delay_ms"] < 30_000.0


@pytest.mark.django_db
@pytest.mark.req("NFR-042")
def test_issuance_boundaries_in_app_and_email() -> None:
    """NFR-042 & A-06: Verifies issuance boundary definitions for IN_APP and EMAIL channels.

    - IN_APP issuance: Persisted in database and immediately queryable via inbox API selector.
    - EMAIL issuance: Handed off to SMTP delivery dispatcher / Mailpit sandbox with DELIVERED status.
    - System explicitly documents that SMTP handoff constitutes issuance, without claiming an
      unmeasured external end-user mailbox delivery guarantee.
    """
    passenger_id = uuid.uuid4()
    Subscription.objects.create(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="line-green",
        active=True,
    )

    event_id = uuid.uuid4()
    occurred_at = datetime.datetime.now(datetime.UTC)

    raw_message = {
        "eventId": str(event_id),
        "type": "DisruptionReported",
        "version": 1,
        "producer": "core-backend",
        "occurredAt": occurred_at.isoformat(),
        "correlationId": str(uuid.uuid4()),
        "payload": {
            "changeType": ChangeType.DISRUPTION,
            "entityType": EntityType.LINE,
            "entityId": "line-green",
            "title": "Green Line Switch Delay",
            "description": "Switch malfunction at Junction 4.",
        },
    }

    t0 = time.perf_counter()
    handle_event_message(raw_message)
    t1 = time.perf_counter()

    elapsed = t1 - t0
    assert elapsed < 30.0

    # 1. IN_APP boundary: immediately visible in passenger inbox query
    inbox_items = list_passenger_notifications(passenger_id=passenger_id)
    assert len(inbox_items) == 1
    assert inbox_items[0].event_id == event_id
    assert inbox_items[0].title == "Green Line Switch Delay"

    # 2. EMAIL boundary: record created with provider acceptance/handoff
    email_rec = NotificationRecord.objects.get(
        event_id=event_id,
        passenger_id=passenger_id,
        channel=NotificationChannel.EMAIL,
    )
    assert email_rec.status == DeliveryStatus.DELIVERED
    assert email_rec.attempts == 1


@pytest.mark.django_db
@pytest.mark.req("NFR-042")
def test_high_fanout_nominal_load_scalability() -> None:
    """NFR-042: Benchmark scalability under 200 subscribers across multiple events."""
    benchmark_result = run_notification_latency_benchmark(
        num_subscribers=200,
        num_events=3,
        line_id="line-silver",
        stop_id="stop-airport",
        target_threshold_seconds=30.0,
    )

    assert benchmark_result.meets_target is True
    assert benchmark_result.max_ms < 30_000.0
    # Mean latency should be far lower than 30s target (typically < 1000ms)
    assert benchmark_result.mean_ms < 5_000.0
    assert benchmark_result.total_notifications_issued == 200 * 2 * 3  # 200 subs * 2 channels * 3 events


@pytest.mark.django_db
@pytest.mark.req("NFR-042")
def test_measure_notification_delay_management_command() -> None:
    """NFR-042: Management command measure_notification_delay executes benchmark and reports metrics."""
    # Run command with 20 subscribers and 2 events
    call_command("measure_notification_delay", subscribers=20, events=2, target=30.0)

    # Verify notification records were created by the benchmark
    records_count = NotificationRecord.objects.count()
    assert records_count == 20 * 2 * 2  # 20 subs * 2 channels * 2 events
