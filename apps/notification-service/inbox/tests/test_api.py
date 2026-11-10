import uuid
from collections.abc import Callable

import pytest
from rest_framework.test import APIClient

from inbox.models import InboxNotification
from inbox.services import create_inbox_notification


@pytest.mark.django_db
@pytest.mark.req("NFR-050")
def test_unauthenticated_inbox_rejected() -> None:
    client = APIClient()
    response = client.get("/api/notifications/v1/inbox")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.django_db
@pytest.mark.req("NFR-050")
def test_staff_cannot_access_passenger_inbox(staff_client: Callable[[uuid.UUID], APIClient]) -> None:
    client = staff_client(uuid.uuid4())
    response = client.get("/api/notifications/v1/inbox")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
@pytest.mark.req("FR-067", "FR-102")
def test_passenger_inbox_listing_and_isolation(
    passenger_client: Callable[[uuid.UUID], APIClient],
) -> None:
    passenger_a = uuid.uuid4()
    passenger_b = uuid.uuid4()

    client_a = passenger_client(passenger_a)
    client_b = passenger_client(passenger_b)

    # Empty inbox
    empty_resp = client_a.get("/api/notifications/v1/inbox")
    assert empty_resp.status_code == 200
    assert empty_resp.json()["items"] == []
    assert empty_resp.json()["unreadCount"] == 0

    # Seed notifications for passenger A
    notif1, _ = create_inbox_notification(
        passenger_id=passenger_a,
        event_id=uuid.uuid4(),
        title="Line Yellow Disruption",
        body="Service suspended between Rato and Saldanha.",
        change_type="DISRUPTION",
        entity_type="LINE",
        entity_id="L-YELLOW",
    )
    notif2, _ = create_inbox_notification(
        passenger_id=passenger_a,
        event_id=uuid.uuid4(),
        title="Trip Delay",
        body="Trip 402 is delayed by 8 minutes.",
        change_type="DELAY",
        entity_type="TRIP",
        entity_id="T-402",
    )

    # Seed notification for passenger B
    create_inbox_notification(
        passenger_id=passenger_b,
        event_id=uuid.uuid4(),
        title="Stop Closed",
        body="Stop Rossio is closed.",
        change_type="DISRUPTION",
        entity_type="STOP",
        entity_id="S-ROSSIO",
    )

    # Passenger A sees only their 2 notifications
    resp_a = client_a.get("/api/notifications/v1/inbox")
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert data_a["unreadCount"] == 2
    assert len(data_a["items"]) == 2
    titles_a = [n["title"] for n in data_a["items"]]
    assert "Line Yellow Disruption" in titles_a
    assert "Trip Delay" in titles_a

    # Passenger B sees only their 1 notification
    resp_b = client_b.get("/api/notifications/v1/inbox")
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["unreadCount"] == 1
    assert len(data_b["items"]) == 1
    assert data_b["items"][0]["title"] == "Stop Closed"


@pytest.mark.django_db
@pytest.mark.req("FR-067", "FR-102")
def test_mark_single_notification_read(passenger_client: Callable[[uuid.UUID], APIClient]) -> None:
    passenger_a = uuid.uuid4()
    passenger_b = uuid.uuid4()

    client_a = passenger_client(passenger_a)
    client_b = passenger_client(passenger_b)

    notif, _ = create_inbox_notification(
        passenger_id=passenger_a,
        event_id=uuid.uuid4(),
        title="Disruption Alert",
        body="Notice body",
        change_type="DISRUPTION",
    )

    # Passenger B cannot mark Passenger A's notification as read
    res_b = client_b.post(f"/api/notifications/v1/inbox/{notif.id}/read")
    assert res_b.status_code == 404

    # Passenger A marks it as read
    res_a = client_a.post(f"/api/notifications/v1/inbox/{notif.id}/read")
    assert res_a.status_code == 200
    assert res_a.json()["read"] is True
    assert res_a.json()["readAt"] is not None

    # Verify unreadCount updated to 0
    inbox_res = client_a.get("/api/notifications/v1/inbox")
    assert inbox_res.json()["unreadCount"] == 0

    # Filtering unread_only returns empty list
    unread_res = client_a.get("/api/notifications/v1/inbox?unread_only=true")
    assert unread_res.json()["items"] == []


@pytest.mark.django_db
@pytest.mark.req("FR-067")
def test_mark_all_notifications_read(passenger_client: Callable[[uuid.UUID], APIClient]) -> None:
    passenger_id = uuid.uuid4()
    client = passenger_client(passenger_id)

    # Create 3 unread notifications
    for i in range(3):
        create_inbox_notification(
            passenger_id=passenger_id,
            event_id=uuid.uuid4(),
            title=f"Alert {i}",
            body=f"Body {i}",
            change_type="DELAY",
        )

    # Check initially 3 unread
    assert client.get("/api/notifications/v1/inbox").json()["unreadCount"] == 3

    # Mark all read
    mark_all_resp = client.post("/api/notifications/v1/inbox/read-all")
    assert mark_all_resp.status_code == 200
    assert mark_all_resp.json()["markedCount"] == 3

    # Now unreadCount is 0
    assert client.get("/api/notifications/v1/inbox").json()["unreadCount"] == 0
    assert InboxNotification.objects.filter(passenger_id=passenger_id, read_at__isnull=True).count() == 0
