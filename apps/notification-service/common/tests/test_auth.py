import datetime
import uuid

import jwt
import pytest
from django.conf import settings
from django.test import RequestFactory
from rest_framework.exceptions import AuthenticationFailed

from common.auth import JWTAuthentication


@pytest.mark.unit
@pytest.mark.req("NFR-050")
def test_jwt_auth_no_header_returns_none() -> None:
    factory = RequestFactory()
    request = factory.get("/health/live")

    authenticator = JWTAuthentication()
    assert authenticator.authenticate(request) is None


@pytest.mark.unit
@pytest.mark.req("NFR-050")
def test_jwt_auth_invalid_header_raises_authentication_failed() -> None:
    factory = RequestFactory()
    request = factory.get("/health/live", HTTP_AUTHORIZATION="Basic 12345")

    authenticator = JWTAuthentication()
    with pytest.raises(AuthenticationFailed):
        authenticator.authenticate(request)


@pytest.mark.unit
@pytest.mark.req("NFR-050")
def test_jwt_auth_valid_token_authenticates_user(private_key: str) -> None:
    user_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": str(user_id),
        "role": "passenger",
        "exp": int((now + datetime.timedelta(hours=1)).timestamp()),
        "iss": settings.JWT_ISSUER,
    }
    token = jwt.encode(payload, private_key, algorithm="RS256")

    factory = RequestFactory()
    request = factory.get("/health/live", HTTP_AUTHORIZATION=f"Bearer {token}")

    authenticator = JWTAuthentication()
    result = authenticator.authenticate(request)

    assert result is not None
    user, claims = result
    assert user.id == user_id
    assert user.role == "passenger"
    assert user.is_authenticated is True
    assert claims["sub"] == str(user_id)


@pytest.mark.unit
@pytest.mark.req("NFR-050")
def test_jwt_auth_expired_token_raises_authentication_failed(private_key: str) -> None:
    user_id = uuid.uuid4()
    past = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
    payload = {
        "sub": str(user_id),
        "role": "passenger",
        "exp": int(past.timestamp()),
        "iss": settings.JWT_ISSUER,
    }
    token = jwt.encode(payload, private_key, algorithm="RS256")

    factory = RequestFactory()
    request = factory.get("/health/live", HTTP_AUTHORIZATION=f"Bearer {token}")

    authenticator = JWTAuthentication()
    with pytest.raises(AuthenticationFailed):
        authenticator.authenticate(request)
