import uuid

import pytest

from preferences.models import NotificationChannel, NotificationPreference


@pytest.mark.unit
@pytest.mark.req("FR-062")
def test_notification_preference_instantiation() -> None:
    passenger_id = uuid.uuid4()
    pref = NotificationPreference(
        passenger_id=passenger_id,
        channel=NotificationChannel.IN_APP,
        enabled=True,
        enabled_change_types=["DISRUPTION", "DELAY"],
    )

    assert pref.passenger_id == passenger_id
    assert pref.channel == NotificationChannel.IN_APP
    assert pref.enabled is True
    assert pref.enabled_change_types == ["DISRUPTION", "DELAY"]
    assert "IN_APP" in str(pref)


@pytest.mark.unit
@pytest.mark.req("FR-062")
def test_notification_preference_table_name() -> None:
    assert NotificationPreference._meta.db_table == "notification_preferences"
