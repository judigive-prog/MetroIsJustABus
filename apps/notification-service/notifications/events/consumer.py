from collections.abc import Callable, Sequence
from typing import Any

import pika
import structlog
from django.conf import settings

from notifications.events.handler import handle_event_message
from notifications.models import NotificationRecord
from notifications.services import RelevantChangeEvent

logger = structlog.get_logger(__name__)

DEFAULT_EXCHANGE = "metro.events"
DEFAULT_QUEUE = "notification-service.events"
DEFAULT_DLX = "metro.events.dlx"
DEFAULT_DLQ = "notification-service.events.dlq"
DEFAULT_ROUTING_KEYS = ("core.#", "metro.#", "disruptions.#", "schedule.#", "trip.#")


class NotificationEventConsumer:
    """AMQP consumer for processing notification-triggering events from RabbitMQ (conventions.md, Events).

    Supports durable queue topology, dead-letter routing, at-least-once deduplication via inbox_event,
    outage recovery, and batch or continuous consumption modes.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        exchange: str = DEFAULT_EXCHANGE,
        queue: str = DEFAULT_QUEUE,
        dlx: str = DEFAULT_DLX,
        dlq: str = DEFAULT_DLQ,
        routing_keys: Sequence[str] = DEFAULT_ROUTING_KEYS,
        connection: Any | None = None,
        channel: Any | None = None,
        dispatchers: dict[str, Callable[[RelevantChangeEvent, Any], None]] | None = None,
        topology_resolver: Callable[[str, str], Sequence[tuple[str, str]]] | None = None,
        raise_on_error: bool = False,
    ) -> None:
        self.host = host or getattr(settings, "RABBITMQ_HOST", "localhost")
        self.port = port or getattr(settings, "RABBITMQ_PORT", 5672)
        self.user = user or getattr(settings, "RABBITMQ_USER", "guest")
        self.password = password or getattr(settings, "RABBITMQ_PASSWORD", "")
        self.exchange = exchange
        self.queue = queue
        self.dlx = dlx
        self.dlq = dlq
        self.routing_keys = tuple(routing_keys)

        self.connection = connection
        self.channel = channel
        self.dispatchers = dispatchers
        self.topology_resolver = topology_resolver
        self.raise_on_error = raise_on_error
        self._is_consuming = False

    def connect(self) -> None:
        """Establish connection and channel if not already supplied."""
        if self.connection is None or self.connection.is_closed:
            credentials = pika.PlainCredentials(self.user, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
                heartbeat=60,
                blocked_connection_timeout=300,
            )
            self.connection = pika.BlockingConnection(parameters)

        if self.channel is None or self.channel.is_closed:
            self.channel = self.connection.channel()

    def setup_topology(self) -> None:
        """Declare durable exchanges, queues, dead-letter bindings, and routing bindings."""
        if self.channel is None:
            self.connect()

        # 1. Dead-letter exchange and durable DLQ
        self.channel.exchange_declare(
            exchange=self.dlx,
            exchange_type="topic",
            durable=True,
        )
        self.channel.queue_declare(
            queue=self.dlq,
            durable=True,
        )
        self.channel.queue_bind(
            queue=self.dlq,
            exchange=self.dlx,
            routing_key="#",
        )

        # 2. Main durable event topic exchange
        self.channel.exchange_declare(
            exchange=self.exchange,
            exchange_type="topic",
            durable=True,
        )

        # 3. Durable consumer queue bound with dead-letter arguments
        queue_args = {
            "x-dead-letter-exchange": self.dlx,
            "x-dead-letter-routing-key": self.dlq,
        }
        self.channel.queue_declare(
            queue=self.queue,
            durable=True,
            arguments=queue_args,
        )

        # 4. Bind routing keys
        for key in self.routing_keys:
            self.channel.queue_bind(
                queue=self.queue,
                exchange=self.exchange,
                routing_key=key,
            )

        logger.info(
            "notification_amqp_topology_declared",
            exchange=self.exchange,
            queue=self.queue,
            dlx=self.dlx,
            dlq=self.dlq,
            routing_keys=self.routing_keys,
        )

    def on_message(
        self,
        channel: Any,
        method: Any,
        properties: Any,
        body: bytes | str,
    ) -> tuple[bool, str, list[NotificationRecord]]:
        """Process incoming event message.

        On success: acks message.
        On poison / invalid message: nacks without requeue (routing message to DLQ).
        """
        delivery_tag = getattr(method, "delivery_tag", None)
        try:
            success, status, records = handle_event_message(
                raw_message=body,
                dispatchers=self.dispatchers,
                raise_on_failure=self.raise_on_error,
                topology_resolver=self.topology_resolver,
            )
            if channel and delivery_tag is not None:
                channel.basic_ack(delivery_tag=delivery_tag)
            return success, status, records
        except Exception as exc:
            logger.error(
                "event_consumption_failed_nacking_to_dlq",
                delivery_tag=delivery_tag,
                error=str(exc),
            )
            if channel and delivery_tag is not None:
                channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
            if self.raise_on_error:
                raise
            return False, f"failed: {exc}", []

    def consume_batch(self, max_messages: int = 100) -> int:
        """Consume up to max_messages synchronously using basic_get.

        Used for testing outage recovery, draining queues, or scheduled reconciliation.
        Returns the count of messages processed.
        """
        if self.channel is None:
            self.connect()

        processed = 0
        while processed < max_messages:
            method_frame, header_frame, body = self.channel.basic_get(
                queue=self.queue,
                auto_ack=False,
            )
            if method_frame is None:
                break

            self.on_message(
                channel=self.channel,
                method=method_frame,
                properties=header_frame,
                body=body,
            )
            processed += 1

        logger.info("consume_batch_completed", count=processed)
        return processed

    def start_consuming(self) -> None:
        """Start listening for incoming events continuously."""
        self.setup_topology()
        self.channel.basic_qos(prefetch_count=10)
        self.channel.basic_consume(
            queue=self.queue,
            on_message_callback=self.on_message,
        )
        self._is_consuming = True
        logger.info("notification_consumer_started", queue=self.queue)
        try:
            self.channel.start_consuming()
        except Exception:
            self._is_consuming = False
            raise

    def stop(self) -> None:
        """Gracefully stop consuming and close channel/connection."""
        if self._is_consuming and self.channel and not self.channel.is_closed:
            try:
                self.channel.stop_consuming()
            except Exception as exc:
                logger.warning("consumer_stop_consuming_failed", error=str(exc))
        self._is_consuming = False

        if self.channel and not self.channel.is_closed:
            try:
                self.channel.close()
            except Exception:
                pass

        if self.connection and not self.connection.is_closed:
            try:
                self.connection.close()
            except Exception:
                pass

        logger.info("notification_consumer_stopped")
