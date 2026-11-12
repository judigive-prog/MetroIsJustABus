import uuid

import pytest

from subscriptions.models import EntityType, Subscription


@pytest.mark.unit
@pytest.mark.req("FR-060")
def test_subscription_model_instantiation() -> None:
    passenger_id = uuid.uuid4()
    sub = Subscription(
        passenger_id=passenger_id,
        entity_type=EntityType.LINE,
        entity_id="LINE-1",
        active=True,
    )

    assert sub.passenger_id == passenger_id
    assert sub.entity_type == EntityType.LINE
    assert sub.entity_id == "LINE-1"
    assert sub.active is True
    assert "LINE-1" in str(sub)


@pytest.mark.unit
@pytest.mark.req("FR-060")
def test_subscription_meta_table_name() -> None:
    assert Subscription._meta.db_table == "subscriptions"
