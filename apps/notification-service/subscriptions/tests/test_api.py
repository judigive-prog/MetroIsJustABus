import uuid
from collections.abc import Callable

import pytest
from rest_framework.test import APIClient

from subscriptions.models import Subscription


@pytest.mark.django_db
@pytest.mark.req("NFR-050")
def test_unauthenticated_subscriptions_rejected() -> None:
    client = APIClient()
    response = client.post(
        "/api/notifications/v1/subscriptions",
        {"entityType": "LINE", "entityId": "L-BLUE"},
        format="json",
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.django_db
@pytest.mark.req("NFR-050")
def test_staff_cannot_create_passenger_subscription(staff_client: Callable[[uuid.UUID], APIClient]) -> None:
    staff_id = uuid.uuid4()
    client = staff_client(staff_id)
    response = client.post(
        "/api/notifications/v1/subscriptions",
        {"entityType": "LINE", "entityId": "L-BLUE"},
        format="json",
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
@pytest.mark.req("FR-060")
def test_passenger_can_subscribe_to_line_stop_and_trip(
    passenger_client: Callable[[uuid.UUID], APIClient],
) -> None:
    passenger_id = uuid.uuid4()
    client = passenger_client(passenger_id)

    # 1. Line
    resp_line = client.post(
        "/api/notifications/v1/subscriptions",
        {"entityType": "LINE", "entityId": "L-BLUE"},
        format="json",
    )
    assert resp_line.status_code == 201
    data_line = resp_line.json()
    assert data_line["entityType"] == "LINE"
    assert data_line["entityId"] == "L-BLUE"
    assert data_line["active"] is True
    assert "id" in data_line

    # 2. Stop
    resp_stop = client.post(
        "/api/notifications/v1/subscriptions",
        {"entityType": "STOP", "entityId": "S-ROSSIO"},
        format="json",
    )
    assert resp_stop.status_code == 201
    data_stop = resp_stop.json()
    assert data_stop["entityType"] == "STOP"
    assert data_stop["entityId"] == "S-ROSSIO"
    assert data_stop["active"] is True

    # 3. Trip
    resp_trip = client.post(
        "/api/notifications/v1/subscriptions",
        {"entityType": "TRIP", "entityId": "T-1004"},
        format="json",
    )
    assert resp_trip.status_code == 201
    data_trip = resp_trip.json()
    assert data_trip["entityType"] == "TRIP"
    assert data_trip["entityId"] == "T-1004"
    assert data_trip["active"] is True

    assert Subscription.objects.filter(passenger_id=passenger_id).count() == 3


@pytest.mark.django_db
@pytest.mark.req("FR-060")
def test_duplicate_active_subscription_returns_conflict(
    passenger_client: Callable[[uuid.UUID], APIClient],
) -> None:
    passenger_id = uuid.uuid4()
    client = passenger_client(passenger_id)

    resp1 = client.post(
        "/api/notifications/v1/subscriptions",
        {"entityType": "LINE", "entityId": "L-BLUE"},
        format="json",
    )
    assert resp1.status_code == 201

    resp2 = client.post(
        "/api/notifications/v1/subscriptions",
        {"entityType": "LINE", "entityId": "L-BLUE"},
        format="json",
    )
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "SUBSCRIPTION_ALREADY_EXISTS"


@pytest.mark.django_db
@pytest.mark.req("FR-060")
def test_invalid_entity_type_rejected(passenger_client: Callable[[uuid.UUID], APIClient]) -> None:
    client = passenger_client(uuid.uuid4())
    response = client.post(
        "/api/notifications/v1/subscriptions",
        {"entityType": "INVALID", "entityId": "L-BLUE"},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
@pytest.mark.req("FR-061", "FR-102")
def test_passenger_subscription_isolation_and_listing(
    passenger_client: Callable[[uuid.UUID], APIClient],
) -> None:
    passenger_a = uuid.uuid4()
    passenger_b = uuid.uuid4()

    client_a = passenger_client(passenger_a)
    client_b = passenger_client(passenger_b)

    # Passenger A creates two subscriptions
    client_a.post(
        "/api/notifications/v1/subscriptions",
        {"entityType": "LINE", "entityId": "L-RED"},
        format="json",
    )
    client_a.post(
        "/api/notifications/v1/subscriptions",
        {"entityType": "STOP", "entityId": "S-ORIENTE"},
        format="json",
    )

    # Passenger B sees nothing
    resp_b = client_b.get("/api/notifications/v1/subscriptions")
    assert resp_b.status_code == 200
    assert resp_b.json()["items"] == []

    # Passenger A sees only their 2 subscriptions
    resp_a = client_a.get("/api/notifications/v1/subscriptions")
    assert resp_a.status_code == 200
    items_a = resp_a.json()["items"]
    assert len(items_a) == 2
    entities = {(item["entityType"], item["entityId"]) for item in items_a}
    assert entities == {("LINE", "L-RED"), ("STOP", "S-ORIENTE")}


@pytest.mark.django_db
@pytest.mark.req("FR-061", "FR-102")
def test_passenger_can_update_and_cancel_subscription(
    passenger_client: Callable[[uuid.UUID], APIClient],
) -> None:
    passenger_a = uuid.uuid4()
    passenger_b = uuid.uuid4()

    client_a = passenger_client(passenger_a)
    client_b = passenger_client(passenger_b)

    create_resp = client_a.post(
        "/api/notifications/v1/subscriptions",
        {"entityType": "LINE", "entityId": "L-GREEN"},
        format="json",
    )
    sub_id = create_resp.json()["id"]

    # Passenger B cannot update Passenger A's subscription
    patch_b = client_b.patch(f"/api/notifications/v1/subscriptions/{sub_id}", {"active": False}, format="json")
    assert patch_b.status_code == 404

    # Passenger B cannot delete Passenger A's subscription
    del_b = client_b.delete(f"/api/notifications/v1/subscriptions/{sub_id}")
    assert del_b.status_code == 404

    # Passenger A can cancel their subscription
    del_a = client_a.delete(f"/api/notifications/v1/subscriptions/{sub_id}")
    assert del_a.status_code == 204

    sub = Subscription.objects.get(id=sub_id)
    assert sub.active is False

    # Passenger A can reactivate by subscribing again
    reactivate_resp = client_a.post(
        "/api/notifications/v1/subscriptions",
        {"entityType": "LINE", "entityId": "L-GREEN"},
        format="json",
    )
    assert reactivate_resp.status_code == 201
    assert reactivate_resp.json()["active"] is True
    sub.refresh_from_db()
    assert sub.active is True
