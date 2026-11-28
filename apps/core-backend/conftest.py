import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings

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
    """Configure Django settings with an ephemeral RS256 test keypair."""
    settings.JWT_PRIVATE_KEY = _TEST_PRIVATE_PEM
    settings.JWT_PUBLIC_KEY = _TEST_PUBLIC_PEM
    settings.JWT_ISSUER = "test-core-backend"
    settings.JWT_KEY_ID = "test-core-rs256"
