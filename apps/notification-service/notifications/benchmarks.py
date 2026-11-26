import datetime
import statistics
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import structlog

from notifications.events.handler import handle_event_message
from notifications.models import DeliveryStatus, NotificationRecord
from preferences.models import ChangeType, NotificationChannel, NotificationPreference
from subscriptions.models import EntityType, Subscription

logger = structlog.get_logger(__name__)

DEFAULT_TARGET_THRESHOLD_SECONDS = 30.0


@dataclass(frozen=True)
class LatencyBenchmarkResult:
    """Stores benchmark results for notification delay measurement (NFR-042)."""

    num_subscribers: int
    num_events: int
    total_notifications_issued: int
    elapsed_total_seconds: float
    throughput_notifications_per_sec: float
    latencies_ms: list[float] = field(default_factory=list)
    mean_ms: float = 0.0
    median_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    max_ms: float = 0.0
    target_threshold_seconds: float = DEFAULT_TARGET_THRESHOLD_SECONDS
    meets_target: bool = True

    def summary(self) -> str:
        return (
            f"Notification Latency Benchmark (NFR-042):\n"
            f"  Subscribers: {self.num_subscribers}\n"
            f"  Events: {self.num_events}\n"
            f"  Total Notifications Issued: {self.total_notifications_issued}\n"
            f"  Total Time: {self.elapsed_total_seconds:.3f} s\n"
            f"  Throughput: {self.throughput_notifications_per_sec:.1f} notifs/sec\n"
            f"  Mean Latency: {self.mean_ms:.2f} ms\n"
            f"  Median Latency: {self.median_ms:.2f} ms\n"
            f"  P95 Latency: {self.p95_ms:.2f} ms\n"
            f"  P99 Latency: {self.p99_ms:.2f} ms\n"
            f"  Max Latency: {self.max_ms:.2f} ms\n"
            f"  Target (< {self.target_threshold_seconds}s): {'PASSED' if self.meets_target else 'FAILED'}"
        )


def setup_benchmark_fixtures(
    num_subscribers: int,
    line_id: str = "line-1",
    stop_id: str = "stop-1",
    channels: Sequence[str] = (NotificationChannel.IN_APP, NotificationChannel.EMAIL),
) -> list[uuid.UUID]:
    """Create test passengers with subscriptions and preferences for latency benchmarking."""
    passenger_ids: list[uuid.UUID] = []
    subscriptions_to_create: list[Subscription] = []
    preferences_to_create: list[NotificationPreference] = []

    for i in range(num_subscribers):
        passenger_id = uuid.uuid4()
        passenger_ids.append(passenger_id)

        # Distribute subscriptions: half line, half stop
        entity_type = EntityType.LINE if i % 2 == 0 else EntityType.STOP
        entity_id = line_id if i % 2 == 0 else stop_id

        subscriptions_to_create.append(
            Subscription(
                passenger_id=passenger_id,
                entity_type=entity_type,
                entity_id=entity_id,
                active=True,
            )
        )

        for ch in channels:
            preferences_to_create.append(
                NotificationPreference(
                    passenger_id=passenger_id,
                    channel=ch,
                    enabled=True,
                    enabled_change_types=[
                        ChangeType.DISRUPTION,
                        ChangeType.DELAY,
                        ChangeType.SCHEDULE_CHANGE,
                    ],
                )
            )

    Subscription.objects.bulk_create(subscriptions_to_create)
    NotificationPreference.objects.bulk_create(preferences_to_create)

    return passenger_ids


def run_notification_latency_benchmark(
    num_subscribers: int = 100,
    num_events: int = 5,
    line_id: str = "line-1",
    stop_id: str = "stop-1",
    target_threshold_seconds: float = DEFAULT_TARGET_THRESHOLD_SECONDS,
) -> LatencyBenchmarkResult:
    """Run notification latency benchmark under nominal load and measure elapsed event-to-issuance times (NFR-042)."""
    setup_benchmark_fixtures(num_subscribers=num_subscribers, line_id=line_id, stop_id=stop_id)

    event_latencies_ms: list[float] = []
    total_notifications = 0

    benchmark_start = time.perf_counter()

    for i in range(num_events):
        event_id = uuid.uuid4()
        occurred_at = datetime.datetime.now(datetime.UTC)
        event_type = "DisruptionReported" if i % 2 == 0 else "ScheduleChanged"
        change_type = ChangeType.DISRUPTION if i % 2 == 0 else ChangeType.SCHEDULE_CHANGE

        raw_message = {
            "eventId": str(event_id),
            "type": event_type,
            "version": 1,
            "producer": "core-backend",
            "occurredAt": occurred_at.isoformat(),
            "correlationId": str(uuid.uuid4()),
            "payload": {
                "changeType": change_type,
                "entityType": EntityType.LINE,
                "entityId": line_id,
                "stopIds": [stop_id],
                "title": f"Benchmark Event {i + 1}",
                "description": f"Benchmark disruption payload {i + 1}",
            },
        }

        t0 = time.perf_counter()
        success, status, records = handle_event_message(raw_message)
        t1 = time.perf_counter()

        elapsed_ms = (t1 - t0) * 1000.0
        event_latencies_ms.append(elapsed_ms)
        total_notifications += len(records)

    benchmark_end = time.perf_counter()
    total_elapsed = benchmark_end - benchmark_start

    sorted_latencies = sorted(event_latencies_ms)
    mean_val = statistics.mean(sorted_latencies) if sorted_latencies else 0.0
    median_val = statistics.median(sorted_latencies) if sorted_latencies else 0.0
    p95_idx = int(0.95 * len(sorted_latencies))
    p99_idx = int(0.99 * len(sorted_latencies))
    p95_val = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)] if sorted_latencies else 0.0
    p99_val = sorted_latencies[min(p99_idx, len(sorted_latencies) - 1)] if sorted_latencies else 0.0
    max_val = max(sorted_latencies) if sorted_latencies else 0.0

    throughput = total_notifications / total_elapsed if total_elapsed > 0 else 0.0
    meets_target = (max_val / 1000.0) <= target_threshold_seconds

    return LatencyBenchmarkResult(
        num_subscribers=num_subscribers,
        num_events=num_events,
        total_notifications_issued=total_notifications,
        elapsed_total_seconds=total_elapsed,
        throughput_notifications_per_sec=throughput,
        latencies_ms=sorted_latencies,
        mean_ms=mean_val,
        median_ms=median_val,
        p95_ms=p95_val,
        p99_ms=p99_val,
        max_ms=max_val,
        target_threshold_seconds=target_threshold_seconds,
        meets_target=meets_target,
    )


def measure_event_issuance_timing(
    event_id: uuid.UUID,
    occurred_at: datetime.datetime,
) -> dict[str, Any]:
    """Measure exact event-to-issuance timing for persisted notification records (NFR-042).

    Compares event occurred_at against notification_records created_at timestamps.
    """
    records = list(
        NotificationRecord.objects.filter(
            event_id=event_id,
            status=DeliveryStatus.DELIVERED,
        ).order_by("created_at")
    )

    if not records:
        return {
            "event_id": str(event_id),
            "record_count": 0,
            "min_delay_ms": 0.0,
            "max_delay_ms": 0.0,
            "mean_delay_ms": 0.0,
            "all_within_30s": True,
        }

    delays_ms: list[float] = []
    for r in records:
        # Calculate delta between event occurrence and notification record creation
        delta = (r.created_at - occurred_at).total_seconds() * 1000.0
        # If timestamps are slightly drifted due to clock precision, floor at 0.0
        delays_ms.append(max(0.0, delta))

    max_delay = max(delays_ms)
    min_delay = min(delays_ms)
    mean_delay = statistics.mean(delays_ms)

    return {
        "event_id": str(event_id),
        "record_count": len(records),
        "min_delay_ms": min_delay,
        "max_delay_ms": max_delay,
        "mean_delay_ms": mean_delay,
        "all_within_30s": (max_delay / 1000.0) <= DEFAULT_TARGET_THRESHOLD_SECONDS,
    }
