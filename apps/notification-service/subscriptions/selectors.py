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


def find_active_subscriptions_for_entities(entities: Sequence[tuple[str, str]]) -> QuerySet[Subscription]:
    if not entities:
        return Subscription.objects.none()
    q = Q()
    for entity_type, entity_id in entities:
        q |= Q(entity_type=entity_type, entity_id=entity_id)
    return Subscription.objects.filter(q, active=True)
