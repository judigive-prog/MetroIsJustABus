import uuid
from collections.abc import Callable

import pytest
from rest_framework.test import APIClient

from preferences.selectors import is_channel_enabled_for_passenger


@pytest.mark.django_db
@pytest.mark.req("NFR-050")
def test_unauthenticated_preferences_rejected() -> None:
    client = APIClient()
    response = client.get("/api/notifications/v1/preferences")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.django_db
@pytest.mark.req("NFR-050")
def test_staff_cannot_access_preferences(staff_client: Callable[[uuid.UUID], APIClient]) -> None:
    client = staff_client(uuid.uuid4())
    response = client.get("/api/notifications/v1/preferences")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
@pytest.mark.req("FR-062", "A-06")
def test_default_preferences_for_new_passenger(
    passenger_client: Callable[[uuid.UUID], APIClient],
) -> None:
    passenger_id = uuid.uuid4()
    client = passenger_client(passenger_id)

    response = client.get("/api/notifications/v1/preferences")
    assert response.status_code == 200
    data = response.json()
    assert "preferences" in data
    prefs = {p["channel"]: p for p in data["preferences"]}

    assert "IN_APP" in prefs
    assert prefs["IN_APP"]["enabled"] is True
    assert set(prefs["IN_APP"]["enabledChangeTypes"]) == {"DISRUPTION", "DELAY", "SCHEDULE_CHANGE"}

    assert "EMAIL" in prefs
    assert prefs["EMAIL"]["enabled"] is True
    assert set(prefs["EMAIL"]["enabledChangeTypes"]) == {"DISRUPTION", "DELAY", "SCHEDULE_CHANGE"}


@pytest.mark.django_db
@pytest.mark.req("FR-062", "A-06", "FR-102")
def test_update_bulk_preferences(passenger_client: Callable[[uuid.UUID], APIClient]) -> None:
    passenger_a = uuid.uuid4()
    passenger_b = uuid.uuid4()

    client_a = passenger_client(passenger_a)
    client_b = passenger_client(passenger_b)

    # Passenger A disables email and restricts in-app to disruptions
    payload = {
        "preferences": [
            {
                "channel": "IN_APP",
                "enabled": True,
                "enabledChangeTypes": ["DISRUPTION"],
            },
            {
                "channel": "EMAIL",
                "enabled": False,
                "enabledChangeTypes": [],
            },
        ]
    }
    update_resp = client_a.put("/api/notifications/v1/preferences", payload, format="json")
    assert update_resp.status_code == 200

    # Verify Passenger A's preferences are updated
    get_resp_a = client_a.get("/api/notifications/v1/preferences")
    prefs_a = {p["channel"]: p for p in get_resp_a.json()["preferences"]}
    assert prefs_a["IN_APP"]["enabled"] is True
    assert prefs_a["IN_APP"]["enabledChangeTypes"] == ["DISRUPTION"]
    assert prefs_a["EMAIL"]["enabled"] is False

    # Verify Passenger B's preferences remain default
    get_resp_b = client_b.get("/api/notifications/v1/preferences")
    prefs_b = {p["channel"]: p for p in get_resp_b.json()["preferences"]}
    assert prefs_b["EMAIL"]["enabled"] is True


@pytest.mark.django_db
@pytest.mark.req("FR-062", "A-06")
def test_update_single_channel_preference(passenger_client: Callable[[uuid.UUID], APIClient]) -> None:
    passenger_id = uuid.uuid4()
    client = passenger_client(passenger_id)

    # Disable EMAIL
    resp = client.put(
        "/api/notifications/v1/preferences/EMAIL",
        {"enabled": False, "enabledChangeTypes": []},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["channel"] == "EMAIL"
    assert resp.json()["enabled"] is False

    # Check selector reflects this at event time (FR-068)
    assert is_channel_enabled_for_passenger(passenger_id, "EMAIL", "DISRUPTION") is False
    assert is_channel_enabled_for_passenger(passenger_id, "IN_APP", "DISRUPTION") is True


@pytest.mark.django_db
@pytest.mark.req("FR-062", "A-06")
def test_invalid_channel_or_change_type_rejected(passenger_client: Callable[[uuid.UUID], APIClient]) -> None:
    client = passenger_client(uuid.uuid4())

    # Invalid channel
    resp1 = client.put(
        "/api/notifications/v1/preferences/SMS",
        {"enabled": True, "enabledChangeTypes": ["DISRUPTION"]},
        format="json",
    )
    assert resp1.status_code == 400

    # Invalid change type
    resp2 = client.put(
        "/api/notifications/v1/preferences/IN_APP",
        {"enabled": True, "enabledChangeTypes": ["WEATHER_ALERT"]},
        format="json",
    )
    assert resp2.status_code == 400
    assert resp2.json()["error"]["code"] == "VALIDATION_ERROR"
