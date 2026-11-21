import json
from datetime import timedelta
from io import StringIO

import jwt
import pytest
import structlog
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import AuthSession, User

REGISTER_URL = "/api/core/v1/auth/register"
LOGIN_URL = "/api/core/v1/auth/login"
LOGOUT_URL = "/api/core/v1/auth/logout"
SESSION_URL = "/api/core/v1/auth/session"
JWKS_URL = "/api/core/v1/auth/jwks"


def _register_passenger(
    client: APIClient,
    *,
    email: str = "alice@example.com",
    password: str = "pass-aaaa-1111",
) -> str:
    response = client.post(
        REGISTER_URL,
        {
            "email": email,
            "password": password,
            "fullName": "Alice Silva",
        },
        format="json",
    )
    assert response.status_code == 201
    return str(response.json()["id"])


@pytest.mark.django_db
@pytest.mark.req("FR-021")
@pytest.mark.req("NFR-050")
@pytest.mark.req("NFR-070")
def test_registered_passenger_can_sign_in_access_session_and_end_session() -> None:
    client = APIClient()
    user_id = _register_passenger(client)

    login_response = client.post(
        LOGIN_URL,
        {"email": "  Alice@Example.com  ", "password": "pass-aaaa-1111"},
        format="json",
        HTTP_X_CORRELATION_ID="login-corr-1",
    )

    assert login_response.status_code == 200
    assert login_response["X-Correlation-Id"] == "login-corr-1"
    login_body = login_response.json()
    token = login_body["accessToken"]
    session_id = login_body["sessionId"]
    assert login_body["tokenType"] == "Bearer"
    assert login_body["expiresIn"] == settings.JWT_ACCESS_TTL_SECONDS
    assert login_body["issuedAt"].endswith("Z")
    assert login_body["expiresAt"].endswith("Z")
    assert login_body["user"]["id"] == user_id
    assert login_body["user"]["email"] == "alice@example.com"
    assert login_body["user"]["role"] == "passenger"
    assert "password" not in login_body["user"]
    assert "password_hash" not in login_body["user"]

    session_row = AuthSession.objects.get(id=session_id)
    assert session_row.revoked_at is None

    auth_client = APIClient()
    auth_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    session_response = auth_client.get(SESSION_URL, HTTP_X_CORRELATION_ID="session-corr-2")
    assert session_response.status_code == 200
    assert session_response["X-Correlation-Id"] == "session-corr-2"
    session_body = session_response.json()
    assert session_body["sessionId"] == session_id
    assert session_body["role"] == "passenger"
    assert session_body["user"]["id"] == user_id

    logout_response = auth_client.post(LOGOUT_URL, HTTP_X_CORRELATION_ID="logout-corr-3")
    assert logout_response.status_code == 204
    assert logout_response["X-Correlation-Id"] == "logout-corr-3"

    session_row.refresh_from_db()
    assert session_row.revoked_at is not None

    after_logout_session = auth_client.get(SESSION_URL)
    assert after_logout_session.status_code == 401
    assert after_logout_session.json()["error"]["code"] == "NOT_AUTHENTICATED"

    after_logout_again = auth_client.post(LOGOUT_URL)
    assert after_logout_again.status_code == 401
    assert after_logout_again.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.django_db
@pytest.mark.req("FR-021")
def test_ending_one_session_keeps_other_active_session_valid() -> None:
    client = APIClient()
    _register_passenger(client)

    first_login = client.post(LOGIN_URL, {"email": "alice@example.com", "password": "pass-aaaa-1111"}, format="json")
    second_login = client.post(LOGIN_URL, {"email": "alice@example.com", "password": "pass-aaaa-1111"}, format="json")
    assert first_login.status_code == 200
    assert second_login.status_code == 200

    first_client = APIClient()
    first_client.credentials(HTTP_AUTHORIZATION=f"Bearer {first_login.json()['accessToken']}")
    second_client = APIClient()
    second_client.credentials(HTTP_AUTHORIZATION=f"Bearer {second_login.json()['accessToken']}")

    assert first_client.post(LOGOUT_URL).status_code == 204
    assert first_client.get(SESSION_URL).status_code == 401
    assert second_client.get(SESSION_URL).status_code == 200


@pytest.mark.django_db
@pytest.mark.req("FR-021")
@pytest.mark.req("NFR-063")
@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("alice@example.com", "wrong-aaaa-2222"),
        ("unknown@example.com", "pass-aaaa-1111"),
    ],
)
def test_login_rejects_invalid_credentials(email: str, password: str) -> None:
    client = APIClient()
    _register_passenger(client)

    response = client.post(
        LOGIN_URL,
        {"email": email, "password": password},
        format="json",
        HTTP_X_CORRELATION_ID="bad-login-401",
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "INVALID_CREDENTIALS",
            "message": "Invalid email or password.",
            "correlationId": "bad-login-401",
        }
    }
    assert AuthSession.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.req("FR-021")
def test_login_rejects_disabled_account() -> None:
    client = APIClient()
    user_id = _register_passenger(client)
    User.objects.filter(id=user_id).update(status=User.Status.DISABLED)

    response = client.post(
        LOGIN_URL,
        {"email": "alice@example.com", "password": "pass-aaaa-1111"},
        format="json",
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert AuthSession.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.req("FR-021")
@pytest.mark.req("NFR-063")
@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": "pass-aaaa-1111"},
        {"email": "alice@example.com", "password": ""},
        {"email": "alice@example.com"},
    ],
)
def test_login_rejects_malformed_payload(payload: dict[str, str]) -> None:
    client = APIClient()
    response = client.post(LOGIN_URL, payload, format="json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
@pytest.mark.req("FR-021")
@pytest.mark.req("NFR-050")
def test_session_endpoints_reject_missing_tampered_and_disabled_user_tokens() -> None:
    client = APIClient()
    user_id = _register_passenger(client)

    assert client.get(SESSION_URL).status_code == 401
    assert client.post(LOGOUT_URL).status_code == 401

    bad_client = APIClient()
    bad_client.credentials(HTTP_AUTHORIZATION="Basic abc")
    assert bad_client.get(SESSION_URL).status_code == 401

    login_response = client.post(LOGIN_URL, {"email": "alice@example.com", "password": "pass-aaaa-1111"}, format="json")
    token = login_response.json()["accessToken"]
    tampered = f"{token[:-1]}{'A' if token[-1] != 'A' else 'B'}"

    tampered_client = APIClient()
    tampered_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tampered}")
    assert tampered_client.get(SESSION_URL).status_code == 401

    other_private = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    wrong_key_token = jwt.encode(
        {
            "sub": user_id,
            "jti": login_response.json()["sessionId"],
            "role": "passenger",
            "exp": int((timezone.now() + timedelta(hours=1)).timestamp()),
            "iss": settings.JWT_ISSUER,
        },
        other_private,
        algorithm="RS256",
    )
    wrong_key_client = APIClient()
    wrong_key_client.credentials(HTTP_AUTHORIZATION=f"Bearer {wrong_key_token}")
    assert wrong_key_client.get(SESSION_URL).status_code == 401

    User.objects.filter(id=user_id).update(status=User.Status.DISABLED)
    disabled_client = APIClient()
    disabled_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert disabled_client.get(SESSION_URL).status_code == 401


@pytest.mark.django_db
@pytest.mark.req("FR-021")
def test_jwks_verifies_issued_rs256_access_token() -> None:
    client = APIClient()
    user_id = _register_passenger(client)

    login_response = client.post(LOGIN_URL, {"email": "alice@example.com", "password": "pass-aaaa-1111"}, format="json")
    login_body = login_response.json()
    token = login_body["accessToken"]

    jwks_response = client.get(JWKS_URL)
    assert jwks_response.status_code == 200
    keys = jwks_response.json()["keys"]
    assert len(keys) == 1
    assert keys[0]["alg"] == "RS256"
    assert keys[0]["kid"] == settings.JWT_KEY_ID

    signing_key = jwt.PyJWK(keys[0]).key
    claims = jwt.decode(
        token,
        key=signing_key,
        algorithms=["RS256"],
        issuer=settings.JWT_ISSUER,
        options={"require": ["sub", "exp", "jti"]},
    )
    assert claims["sub"] == user_id
    assert claims["jti"] == login_body["sessionId"]
    assert claims["role"] == "passenger"


@pytest.mark.django_db
@pytest.mark.req("FR-021")
@pytest.mark.req("NFR-051")
@pytest.mark.req("NFR-056")
def test_login_and_logout_do_not_log_passwords_or_tokens() -> None:
    raw_password = "canary-aaaa-1111"
    client = APIClient()
    _register_passenger(client, password=raw_password)

    with structlog.testing.capture_logs() as logs:
        login_response = client.post(LOGIN_URL, {"email": "alice@example.com", "password": raw_password}, format="json")
        assert login_response.status_code == 200
        token = login_response.json()["accessToken"]
        auth_client = APIClient()
        auth_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        assert auth_client.post(LOGOUT_URL).status_code == 204

    serialized = json.dumps(logs)
    assert raw_password not in serialized
    assert token not in serialized
    assert "argon2$argon2id$" not in serialized


@pytest.mark.unit
@pytest.mark.req("FR-021")
def test_openapi_schema_includes_session_endpoints_without_warnings() -> None:
    output = StringIO()
    call_command("spectacular", format="openapi-json", validate=True, fail_on_warn=True, stdout=output)
    schema = json.loads(output.getvalue())

    assert "post" in schema["paths"]["/api/core/v1/auth/login"]
    assert "post" in schema["paths"]["/api/core/v1/auth/logout"]
    assert "get" in schema["paths"]["/api/core/v1/auth/session"]
    assert "get" in schema["paths"]["/api/core/v1/auth/jwks"]
