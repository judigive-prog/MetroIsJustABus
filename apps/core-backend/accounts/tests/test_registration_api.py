import json
from io import StringIO

import pytest
import structlog
from django.core.management import call_command
from rest_framework.test import APIClient

from accounts.models import AccountProfile, RoleAssignment, User

REGISTER_URL = "/api/core/v1/auth/register"


@pytest.mark.django_db
@pytest.mark.req("FR-020")
@pytest.mark.req("NFR-051")
@pytest.mark.req("NFR-070")
def test_register_creates_passenger_account_with_argon2id_credentials() -> None:
    raw_password = "pass-aaaa-1111"
    client = APIClient()

    response = client.post(
        REGISTER_URL,
        {
            "email": "  Alice.Silva@Example.com  ",
            "password": raw_password,
            "fullName": "  Alice Silva  ",
            "phone": "  +351910000000  ",
        },
        format="json",
        HTTP_X_CORRELATION_ID="reg-corr-123",
    )

    assert response.status_code == 201
    assert response["X-Correlation-Id"] == "reg-corr-123"
    body = response.json()
    assert body["email"] == "alice.silva@example.com"
    assert body["fullName"] == "Alice Silva"
    assert body["contactEmail"] == "alice.silva@example.com"
    assert body["phone"] == "+351910000000"
    assert body["role"] == RoleAssignment.Role.PASSENGER
    assert body["status"] == User.Status.ACTIVE
    assert body["createdAt"].endswith("Z")
    assert "password" not in body
    assert "password_hash" not in body
    assert "passwordHash" not in body
    assert raw_password not in response.content.decode("utf-8")

    user = User.objects.get(id=body["id"])
    assert user.email == "alice.silva@example.com"
    assert user.password_hash.startswith("argon2$argon2id$")
    assert user.check_password(raw_password) is True
    assert user.check_password("wrong-password") is False

    profile = AccountProfile.objects.get(user=user)
    assert profile.full_name == "Alice Silva"
    assert profile.contact_email == "alice.silva@example.com"
    assert profile.phone == "+351910000000"

    assignment = RoleAssignment.objects.get(user=user)
    assert assignment.role == RoleAssignment.Role.PASSENGER
    assert assignment.active is True


@pytest.mark.django_db
@pytest.mark.req("FR-020")
def test_register_allows_omitted_phone_and_ignores_bogus_bearer_header() -> None:
    client = APIClient()
    response = client.post(
        REGISTER_URL,
        {
            "email": "bob@example.com",
            "password": "valid-password-123",
            "fullName": "Bob Costa",
        },
        format="json",
        HTTP_AUTHORIZATION="Bearer not-needed-for-signup",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["phone"] == ""
    assert AccountProfile.objects.get(user_id=body["id"]).phone == ""


@pytest.mark.django_db
@pytest.mark.req("FR-020")
@pytest.mark.req("FR-100")
def test_register_ignores_privileged_role_or_status_in_payload() -> None:
    client = APIClient()
    response = client.post(
        REGISTER_URL,
        {
            "email": "carol@example.com",
            "password": "valid-password-123",
            "fullName": "Carol Ferreira",
            "role": "staff",
            "status": "DISABLED",
        },
        format="json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == RoleAssignment.Role.PASSENGER
    assert body["status"] == User.Status.ACTIVE
    assert not RoleAssignment.objects.filter(user_id=body["id"], role=RoleAssignment.Role.STAFF).exists()


@pytest.mark.django_db
@pytest.mark.req("FR-020")
@pytest.mark.req("NFR-063")
def test_register_rejects_duplicate_email_case_insensitively() -> None:
    client = APIClient()
    payload = {
        "email": "alice@example.com",
        "password": "valid-password-123",
        "fullName": "Alice Silva",
    }
    first = client.post(REGISTER_URL, payload, format="json")
    assert first.status_code == 201

    duplicate = client.post(
        REGISTER_URL,
        {
            "email": "Alice@Example.com",
            "password": "another-password-123",
            "fullName": "Alice Duplicate",
        },
        format="json",
        HTTP_X_CORRELATION_ID="dup-corr-409",
    )

    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "error": {
            "code": "ACCOUNT_ALREADY_EXISTS",
            "message": "An account with this email already exists.",
            "correlationId": "dup-corr-409",
        }
    }
    assert User.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.req("FR-020")
@pytest.mark.req("NFR-063")
@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": "valid-password-123", "fullName": "Alice"},
        {"email": "alice@example.com", "password": "short", "fullName": "Alice"},
        {"email": "alice@example.com", "password": "        ", "fullName": "Alice"},
        {"email": "alice@example.com", "password": "valid-password-123", "fullName": "   "},
        {"email": "alice@example.com", "password": "valid-password-123"},
    ],
)
def test_register_rejects_invalid_payloads(payload: dict[str, str]) -> None:
    client = APIClient()
    response = client.post(
        REGISTER_URL,
        payload,
        format="json",
        HTTP_X_CORRELATION_ID="invalid-corr-400",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["correlationId"] == "invalid-corr-400"
    assert User.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.req("FR-020")
@pytest.mark.req("NFR-051")
@pytest.mark.req("NFR-056")
def test_register_does_not_log_plaintext_password_or_hash() -> None:
    raw_password = "canary-aaaa-1111"
    client = APIClient()

    with structlog.testing.capture_logs() as logs:
        response = client.post(
            REGISTER_URL,
            {
                "email": "dave@example.com",
                "password": raw_password,
                "fullName": "Dave Oliveira",
            },
            format="json",
        )

    assert response.status_code == 201
    serialized_logs = json.dumps(logs)
    assert raw_password not in serialized_logs
    assert "argon2$argon2id$" not in serialized_logs


@pytest.mark.unit
@pytest.mark.req("FR-020")
def test_openapi_schema_includes_register_endpoint_without_warnings() -> None:
    output = StringIO()
    call_command("spectacular", format="openapi-json", validate=True, fail_on_warn=True, stdout=output)
    schema = json.loads(output.getvalue())

    register_op = schema["paths"]["/api/core/v1/auth/register"]["post"]
    assert "201" in register_op["responses"]
    assert "400" in register_op["responses"]
    assert "409" in register_op["responses"]
