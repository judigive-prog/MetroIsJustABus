import signal
import sys
from typing import Any

import structlog
from django.core.management.base import BaseCommand

from notifications.events.consumer import NotificationEventConsumer

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Run RabbitMQ consumer for notification-triggering events (NFR-021)"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--batch",
            type=int,
            default=0,
            help="If set > 0, consumes up to this number of messages in batch mode and exits.",
        )
        parser.add_argument(
            "--queue",
            type=str,
            default=None,
            help="Queue name override.",
        )
        parser.add_argument(
            "--exchange",
            type=str,
            default=None,
            help="Exchange name override.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        batch_size = options.get("batch") or 0
        queue_override = options.get("queue")
        exchange_override = options.get("exchange")

        consumer_kwargs: dict[str, Any] = {}
        if queue_override:
            consumer_kwargs["queue"] = queue_override
        if exchange_override:
            consumer_kwargs["exchange"] = exchange_override

        consumer = NotificationEventConsumer(**consumer_kwargs)

        def _handle_exit(signum: int, frame: Any) -> None:
            logger.info("notification_consumer_signal_received", signal=signum)
            consumer.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, _handle_exit)
        signal.signal(signal.SIGTERM, _handle_exit)

        if batch_size > 0:
            self.stdout.write(f"Consuming up to {batch_size} messages in batch mode...")
            processed = consumer.consume_batch(max_messages=batch_size)
            self.stdout.write(self.style.SUCCESS(f"Batch completed: processed {processed} messages."))
            return

        self.stdout.write("Starting continuous notification event consumer...")
        try:
            consumer.start_consuming()
        except KeyboardInterrupt:
            consumer.stop()
            self.stdout.write(self.style.SUCCESS("Consumer stopped cleanly."))
