import uuid
from unittest.mock import MagicMock

import pytest

from common.auth import AuthenticatedUser
from common.permissions import DenyAll, IsPassenger, IsStaff


@pytest.mark.unit
@pytest.mark.req("NFR-050")
def test_deny_all_always_returns_false() -> None:
    permission = DenyAll()
    request = MagicMock()
    view = MagicMock()

    assert permission.has_permission(request, view) is False


@pytest.mark.unit
@pytest.mark.req("FR-100", "FR-102", "NFR-050")
def test_is_passenger_allows_passenger_role() -> None:
    permission = IsPassenger()
    request = MagicMock()
    request.user = AuthenticatedUser(id=uuid.uuid4(), role="passenger")
    view = MagicMock()

    assert permission.has_permission(request, view) is True


@pytest.mark.unit
@pytest.mark.req("FR-102", "NFR-050")
def test_is_passenger_denies_staff_and_anonymous() -> None:
    permission = IsPassenger()
    view = MagicMock()

    # Staff user
    staff_request = MagicMock()
    staff_request.user = AuthenticatedUser(id=uuid.uuid4(), role="staff")
    assert permission.has_permission(staff_request, view) is False

    # Anonymous user
    anon_request = MagicMock()
    anon_request.user = None
    assert permission.has_permission(anon_request, view) is False


@pytest.mark.unit
@pytest.mark.req("FR-101", "NFR-050")
def test_is_staff_allows_staff_role() -> None:
    permission = IsStaff()
    request = MagicMock()
    request.user = AuthenticatedUser(id=uuid.uuid4(), role="staff")
    view = MagicMock()

    assert permission.has_permission(request, view) is True
