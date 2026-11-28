from datetime import timedelta

import jwt
import pytest
from django.conf import settings
from django.test import override_settings
from django.urls import path
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework.views import APIView

from accounts.models import AuthSession, RoleAssignment
from accounts.services import create_user_credentials
from common.permissions import IsAuthenticatedRole, IsPassenger, IsStaff
from config.urls import urlpatterns as base_urlpatterns

REGISTER_URL = "/api/core/v1/auth/register"
LOGIN_URL = "/api/core/v1/auth/login"
LOGOUT_URL = "/api/core/v1/auth/logout"
SESSION_URL = "/api/core/v1/auth/session"
JWKS_URL = "/api/core/v1/auth/jwks"
DEFAULT_DENY_URL = "/_boundary/default-deny"
AUTH_ROLE_URL = "/_boundary/authenticated-role"
PASSENGER_ONLY_URL = "/_boundary/passenger-only"
STAFF_ONLY_URL = "/_boundary/staff-only"


class _DefaultDenyView(APIView):
    def get(self, request: Request) -> Response:
        return Response({"ok": True})


class _AuthenticatedRoleView(APIView):
    permission_classes = [IsAuthenticatedRole]

    def get(self, request: Request) -> Response:
        return Response({"role": request.user.role})


class _PassengerOnlyView(APIView):
    permission_classes = [IsPassenger]

    def get(self, request: Request) -> Response:
        return Response({"role": request.user.role})


class _StaffOnlyView(APIView):
    permission_classes = [IsStaff]

    def get(self, request: Request) -> Response:
        return Response({"role": request.user.role})


urlpatterns = [
    *base_urlpatterns,
    path("_boundary/default-deny", _DefaultDenyView.as_view()),
    path("_boundary/authenticated-role", _AuthenticatedRoleView.as_view()),
    path("_boundary/passenger-only", _PassengerOnlyView.as_view()),
    path("_boundary/staff-only", _StaffOnlyView.as_view()),
]


def _sign_in(client: APIClient, *, email: str, password: str) -> tuple[APIClient, str, str]:
    response = client.post(LOGIN_URL, {"email": email, "password": password}, format="json")
    assert response.status_code == 200
    body = response.json()
    authed = APIClient()
    authed.credentials(HTTP_AUTHORIZATION=f"Bearer {body['accessToken']}")
    return authed, str(body["user"]["id"]), str(body["sessionId"])


@pytest.mark.django_db
@pytest.mark.req("FR-100")
@pytest.mark.req("NFR-050")
def test_visitor_can_access_public_schema_without_authentication() -> None:
    assert APIClient().get("/api/core/v1/schema").status_code == 200


@pytest.mark.django_db
@pytest.mark.req("FR-100")
@pytest.mark.req("NFR-050")
@override_settings(ROOT_URLCONF=__name__)
def test_visitor_access_matrix() -> None:
    visitor = APIClient()

    assert visitor.get("/health/live").status_code == 200
    assert visitor.get(JWKS_URL).status_code == 200
    signup = visitor.post(
        REGISTER_URL,
        {"email": "visitor-signup@example.com", "password": "pass-aaaa-1111", "fullName": "Visitor"},
        format="json",
    )
    assert signup.status_code == 201

    for url, method in [
        (SESSION_URL, visitor.get),
        (LOGOUT_URL, visitor.post),
        (DEFAULT_DENY_URL, visitor.get),
        (AUTH_ROLE_URL, visitor.get),
        (PASSENGER_ONLY_URL, visitor.get),
        (STAFF_ONLY_URL, visitor.get),
    ]:
        response = method(url)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.django_db
@pytest.mark.req("FR-100")
@pytest.mark.req("NFR-050")
@override_settings(ROOT_URLCONF=__name__)
def test_passenger_access_matrix() -> None:
    anon = APIClient()
    register = anon.post(
        REGISTER_URL,
        {"email": "passenger@example.com", "password": "pass-aaaa-1111", "fullName": "Alice Passenger"},
        format="json",
    )
    assert register.status_code == 201

    passenger, _, _ = _sign_in(anon, email="passenger@example.com", password="pass-aaaa-1111")

    assert passenger.get(SESSION_URL).status_code == 200
    assert passenger.get(AUTH_ROLE_URL).json() == {"role": RoleAssignment.Role.PASSENGER}
    assert passenger.get(PASSENGER_ONLY_URL).json() == {"role": RoleAssignment.Role.PASSENGER}

    staff_denied = passenger.get(STAFF_ONLY_URL, HTTP_X_CORRELATION_ID="role-deny-staff")
    assert staff_denied.status_code == 403
    assert staff_denied["X-Correlation-Id"] == "role-deny-staff"
    assert staff_denied.json()["error"]["code"] == "PERMISSION_DENIED"
    assert staff_denied.json()["error"]["correlationId"] == "role-deny-staff"

    default_denied = passenger.get(DEFAULT_DENY_URL)
    assert default_denied.status_code == 403
    assert default_denied.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
@pytest.mark.req("FR-100")
@pytest.mark.req("FR-101")
@pytest.mark.req("NFR-050")
@override_settings(ROOT_URLCONF=__name__)
def test_staff_access_matrix() -> None:
    create_user_credentials(
        email="operator@example.com",
        raw_password="pass-aaaa-1111",
        full_name="Carlos Operator",
        role=RoleAssignment.Role.STAFF,
    )
    staff, _, _ = _sign_in(APIClient(), email="operator@example.com", password="pass-aaaa-1111")

    session_resp = staff.get(SESSION_URL)
    assert session_resp.status_code == 200
    assert session_resp.json()["role"] == RoleAssignment.Role.STAFF
    assert staff.get(AUTH_ROLE_URL).json() == {"role": RoleAssignment.Role.STAFF}
    assert staff.get(STAFF_ONLY_URL).json() == {"role": RoleAssignment.Role.STAFF}

    passenger_denied = staff.get(PASSENGER_ONLY_URL)
    assert passenger_denied.status_code == 403
    assert passenger_denied.json()["error"]["code"] == "PERMISSION_DENIED"

    default_denied = staff.get(DEFAULT_DENY_URL)
    assert default_denied.status_code == 403
    assert default_denied.json()["error"]["code"] == "PERMISSION_DENIED"

    assert staff.post(LOGOUT_URL).status_code == 204
    assert staff.get(STAFF_ONLY_URL).status_code == 401


@pytest.mark.django_db
@pytest.mark.req("FR-100")
@pytest.mark.req("NFR-050")
@override_settings(ROOT_URLCONF=__name__)
@pytest.mark.parametrize("forged_role", ["admin", "service", "passenger", ""])
def test_unrecognized_or_mismatched_role_claim_is_rejected(forged_role: str) -> None:
    create_user_credentials(
        email="staff-claim@example.com",
        raw_password="pass-aaaa-1111",
        full_name="Staff Claim",
        role=RoleAssignment.Role.STAFF,
    )
    _, user_id, session_id = _sign_in(APIClient(), email="staff-claim@example.com", password="pass-aaaa-1111")

    forged_token = jwt.encode(
        {
            "sub": user_id,
            "jti": session_id,
            "role": forged_role,
            "exp": int((timezone.now() + timedelta(hours=1)).timestamp()),
            "iss": settings.JWT_ISSUER,
        },
        settings.JWT_PRIVATE_KEY,
        algorithm="RS256",
    )
    forged_client = APIClient()
    forged_client.credentials(HTTP_AUTHORIZATION=f"Bearer {forged_token}")

    for url in (SESSION_URL, AUTH_ROLE_URL, PASSENGER_ONLY_URL, STAFF_ONLY_URL):
        response = forged_client.get(url)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.django_db
@pytest.mark.req("FR-100")
@pytest.mark.req("FR-101")
@override_settings(ROOT_URLCONF=__name__)
def test_revoking_role_assignment_blocks_active_session_and_login() -> None:
    user = create_user_credentials(
        email="revoked-staff@example.com",
        raw_password="pass-aaaa-1111",
        full_name="Revoked Staff",
        role=RoleAssignment.Role.STAFF,
    )
    staff, _, _ = _sign_in(APIClient(), email="revoked-staff@example.com", password="pass-aaaa-1111")
    assert staff.get(STAFF_ONLY_URL).status_code == 200

    RoleAssignment.objects.filter(user=user, active=True).update(active=False, revoked_at=timezone.now())

    revoked_resp = staff.get(STAFF_ONLY_URL)
    assert revoked_resp.status_code == 401
    assert revoked_resp.json()["error"]["code"] == "NOT_AUTHENTICATED"

    relogin = APIClient().post(
        LOGIN_URL,
        {"email": "revoked-staff@example.com", "password": "pass-aaaa-1111"},
        format="json",
    )
    assert relogin.status_code == 401
    assert relogin.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert AuthSession.objects.filter(user=user).count() == 1
