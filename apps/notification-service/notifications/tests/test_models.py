import uuid

import pytest

from notifications.models import DeliveryStatus, NotificationRecord
from preferences.models import NotificationChannel


@pytest.mark.unit
@pytest.mark.req("FR-066")
def test_notification_record_instantiation() -> None:
    event_id = uuid.uuid4()
    passenger_id = uuid.uuid4()
    record = NotificationRecord(
        event_id=event_id,
        passenger_id=passenger_id,
        channel=NotificationChannel.IN_APP,
        status=DeliveryStatus.PENDING,
        attempts=0,
    )

    assert record.event_id == event_id
    assert record.passenger_id == passenger_id
    assert record.channel == NotificationChannel.IN_APP
    assert record.status == DeliveryStatus.PENDING
    assert record.attempts == 0
    assert "PENDING" in str(record)


@pytest.mark.unit
@pytest.mark.req("FR-066")
def test_notification_record_table_name() -> None:
    assert NotificationRecord._meta.db_table == "notification_records"
