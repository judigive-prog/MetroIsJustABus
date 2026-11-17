import uuid
from unittest.mock import MagicMock

import pytest

from common.auth import AuthenticatedUser
from common.permissions import DenyAll, IsPassenger, IsStaff


@pytest.mark.unit
@pytest.mark.req("NFR-050")
def test_deny_all_always_returns_false() -> None:
    assert DenyAll().has_permission(MagicMock(), MagicMock()) is False


@pytest.mark.unit
@pytest.mark.req("FR-100")
@pytest.mark.req("NFR-050")
def test_is_passenger_allows_only_passenger_role() -> None:
    permission = IsPassenger()
    view = MagicMock()

    passenger_req = MagicMock(user=AuthenticatedUser(id=uuid.uuid4(), role="passenger"))
    staff_req = MagicMock(user=AuthenticatedUser(id=uuid.uuid4(), role="staff"))
    anon_req = MagicMock(user=None)

    assert permission.has_permission(passenger_req, view) is True
    assert permission.has_permission(staff_req, view) is False
    assert permission.has_permission(anon_req, view) is False


@pytest.mark.unit
@pytest.mark.req("FR-100")
@pytest.mark.req("FR-101")
@pytest.mark.req("NFR-050")
def test_is_staff_allows_only_staff_role() -> None:
    permission = IsStaff()
    view = MagicMock()

    staff_req = MagicMock(user=AuthenticatedUser(id=uuid.uuid4(), role="staff"))
    passenger_req = MagicMock(user=AuthenticatedUser(id=uuid.uuid4(), role="passenger"))
    anon_req = MagicMock(user=None)

    assert permission.has_permission(staff_req, view) is True
    assert permission.has_permission(passenger_req, view) is False
    assert permission.has_permission(anon_req, view) is False
