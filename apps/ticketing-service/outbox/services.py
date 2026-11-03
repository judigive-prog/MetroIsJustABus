from django.db import transaction
from metro_common.events import EventEnvelope

from outbox.models import OutboxEvent


def enqueue(*, envelope: EventEnvelope, routing_key: str) -> OutboxEvent:
    """Store an event in the caller's transaction. Never publishes directly (principle: outbox only)."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("outbox.enqueue must run inside the transaction that changes state")
    return OutboxEvent.objects.create(
        event_id=envelope.event_id,
        event_type=envelope.type,
        routing_key=routing_key,
        body=envelope.model_dump(mode="json", by_alias=True),
    )
