import uuid

import structlog
from django.db import transaction

from subscriptions.exceptions import InvalidEntityType, SubscriptionAlreadyExists, SubscriptionNotFound
from subscriptions.models import EntityType, Subscription
from subscriptions.selectors import get_subscription

logger = structlog.get_logger(__name__)


def create_subscription(passenger_id: uuid.UUID, entity_type: str, entity_id: str) -> Subscription:
    if entity_type not in EntityType.values:
        raise InvalidEntityType()

    entity_id = entity_id.strip()
    if not entity_id:
        raise InvalidEntityType()

    with transaction.atomic():
        existing = (
            Subscription.objects.select_for_update()
            .filter(
                passenger_id=passenger_id,
                entity_type=entity_type,
                entity_id=entity_id,
            )
            .first()
        )

        if existing:
            if existing.active:
                raise SubscriptionAlreadyExists()
            existing.active = True
            existing.save(update_fields=["active", "updated_at"])
            logger.info(
                "subscription_reactivated",
                subscription_id=str(existing.id),
                passenger_id=str(passenger_id),
                entity_type=entity_type,
                entity_id=entity_id,
            )
            return existing

        subscription = Subscription.objects.create(
            passenger_id=passenger_id,
            entity_type=entity_type,
            entity_id=entity_id,
            active=True,
        )
        logger.info(
            "subscription_created",
            subscription_id=str(subscription.id),
            passenger_id=str(passenger_id),
            entity_type=entity_type,
            entity_id=entity_id,
        )
        return subscription


def update_subscription_status(subscription_id: uuid.UUID, passenger_id: uuid.UUID, active: bool) -> Subscription:
    subscription = get_subscription(subscription_id=subscription_id, passenger_id=passenger_id)
    if not subscription:
        raise SubscriptionNotFound()

    subscription.active = active
    subscription.save(update_fields=["active", "updated_at"])
    logger.info(
        "subscription_status_updated",
        subscription_id=str(subscription.id),
        passenger_id=str(passenger_id),
        active=active,
    )
    return subscription


def cancel_subscription(subscription_id: uuid.UUID, passenger_id: uuid.UUID) -> None:
    update_subscription_status(subscription_id=subscription_id, passenger_id=passenger_id, active=False)
