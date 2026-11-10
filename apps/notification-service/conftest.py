import datetime
import uuid
from collections.abc import Callable

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from rest_framework.test import APIClient

# Generate an ephemeral in-memory 2048-bit RSA keypair for the test session
_TEST_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_TEST_PRIVATE_PEM = _TEST_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("utf-8")
_TEST_PUBLIC_PEM = (
    _TEST_KEY.public_key()
    .public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode("utf-8")
)


@pytest.fixture(autouse=True, scope="session")
def configure_test_jwt_keys() -> None:
    """Configure Django settings with the ephemeral public key."""
    settings.JWT_PUBLIC_KEY = _TEST_PUBLIC_PEM
    settings.JWT_ISSUER = "test-core-backend"


@pytest.fixture
def private_key() -> str:
    return _TEST_PRIVATE_PEM


@pytest.fixture
def make_token(private_key: str) -> Callable[[uuid.UUID, str], str]:
    def _make(user_id: uuid.UUID, role: str = "passenger") -> str:
        now = datetime.datetime.now(datetime.UTC)
        payload = {
            "sub": str(user_id),
            "role": role,
            "exp": int((now + datetime.timedelta(hours=1)).timestamp()),
            "iss": settings.JWT_ISSUER,
        }
        return jwt.encode(payload, private_key, algorithm="RS256")

    return _make


@pytest.fixture
def passenger_client(make_token: Callable[[uuid.UUID, str], str]) -> Callable[[uuid.UUID], APIClient]:
    def _client(passenger_id: uuid.UUID) -> APIClient:
        token = make_token(passenger_id, "passenger")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    return _client


@pytest.fixture
def staff_client(make_token: Callable[[uuid.UUID, str], str]) -> Callable[[uuid.UUID], APIClient]:
    def _client(staff_id: uuid.UUID) -> APIClient:
        token = make_token(staff_id, "staff")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    return _client
