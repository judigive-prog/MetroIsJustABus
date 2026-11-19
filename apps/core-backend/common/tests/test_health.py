import json
from unittest.mock import patch

import pytest
from django.db import DatabaseError
from django.test import RequestFactory

from common import health


@pytest.mark.unit
@pytest.mark.req("NFR-071")
def test_live_probe_returns_200() -> None:
    request = RequestFactory().get("/health/live")

    response = health.live(request)

    assert response.status_code == 200
    assert json.loads(response.content) == {"status": "ok"}


@pytest.mark.unit
@pytest.mark.req("NFR-071")
def test_ready_probe_returns_200_when_database_is_connected() -> None:
    request = RequestFactory().get("/health/ready")

    with patch("common.health.connection.ensure_connection", return_value=None):
        response = health.ready(request)

    assert response.status_code == 200
    assert json.loads(response.content) == {"status": "ok"}


@pytest.mark.unit
@pytest.mark.req("NFR-071")
def test_ready_probe_returns_503_when_database_fails() -> None:
    request = RequestFactory().get("/health/ready")

    with patch("common.health.connection.ensure_connection", side_effect=DatabaseError("Connection refused")):
        response = health.ready(request)

    assert response.status_code == 503
    assert json.loads(response.content) == {"status": "unavailable", "dependency": "database"}
