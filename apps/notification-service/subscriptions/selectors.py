import datetime
import uuid
from typing import Sequence

from django.db.models import Q, QuerySet

from subscriptions.models import Subscription


def get_subscription(subscription_id: uuid.UUID, passenger_id: uuid.UUID) -> Subscription | None:
    return Subscription.objects.filter(id=subscription_id, passenger_id=passenger_id).first()


def list_subscriptions(passenger_id: uuid.UUID, active: bool | None = None) -> QuerySet[Subscription]:
    qs = Subscription.objects.filter(passenger_id=passenger_id)
    if active is not None:
        qs = qs.filter(active=active)
    return qs.order_by("-created_at")


def find_active_subscriptions_for_entities(
    entities: Sequence[tuple[str, str]],
    at_time: datetime.datetime | None = None,
) -> QuerySet[Subscription]:
    """Find active subscriptions for given entities, optionally evaluated at event time (FR-063, FR-068)."""
    if not entities:
        return Subscription.objects.none()
    q = Q()
    for entity_type, entity_id in entities:
        q |= Q(entity_type=entity_type, entity_id=entity_id)

    qs = Subscription.objects.filter(q)
    if at_time is not None:
        # FR-068: Subscriptions active at event time:
        # 1. Created at or before the event occurred.
        # 2. Not cancelled before the event occurred (active or cancelled strictly after event time).
        qs = qs.filter(created_at__lte=at_time).filter(Q(cancelled_at__isnull=True) | Q(cancelled_at__gt=at_time))
    else:
        qs = qs.filter(active=True)
    return qs
