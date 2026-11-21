from typing import Any

from django.core.management.base import BaseCommand

from notifications.benchmarks import run_notification_latency_benchmark


class Command(BaseCommand):
    help = "Benchmark and measure notification issuance delay against the 30-second target (NFR-042)"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--subscribers",
            type=int,
            default=100,
            help="Number of subscribed passengers under nominal load (default: 100).",
        )
        parser.add_argument(
            "--events",
            type=int,
            default=5,
            help="Number of events to generate and process (default: 5).",
        )
        parser.add_argument(
            "--target",
            type=float,
            default=30.0,
            help="Target delay threshold in seconds (default: 30.0).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        subscribers = options.get("subscribers") or 100
        events = options.get("events") or 5
        target = options.get("target") or 30.0

        self.stdout.write(
            f"Starting notification delay benchmark (subscribers={subscribers}, events={events}, target={target}s)..."
        )
        result = run_notification_latency_benchmark(
            num_subscribers=subscribers,
            num_events=events,
            target_threshold_seconds=target,
        )

        self.stdout.write(result.summary())
        if result.meets_target:
            self.stdout.write(self.style.SUCCESS(f"SUCCESS: Notification issuance met the target (< {target}s)."))
        else:
            self.stdout.write(self.style.ERROR(f"FAILURE: Notification issuance exceeded the target (< {target}s)."))
