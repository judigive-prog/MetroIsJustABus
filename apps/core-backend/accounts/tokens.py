"""RS256 access token signing and JWKS serialization (FR-021, DES-01)."""

import base64
import uuid
from datetime import datetime
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from django.conf import settings


def _b64url_uint(value: int) -> str:
    byte_length = max(1, (value.bit_length() + 7) // 8)
    raw = value.to_bytes(byte_length, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def issue_access_token(
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    role: str,
    issued_at: datetime,
    expires_at: datetime,
) -> str:
    """Sign an RS256 access token carrying `sub`, `jti`, `role`, `iat`, `exp`, and `iss`."""
    if not settings.JWT_PRIVATE_KEY:
        raise RuntimeError("JWT_PRIVATE_KEY must be configured to sign access tokens.")

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "jti": str(session_id),
        "role": role,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if settings.JWT_ISSUER:
        payload["iss"] = settings.JWT_ISSUER

    headers = {"kid": settings.JWT_KEY_ID} if getattr(settings, "JWT_KEY_ID", "") else None
    return jwt.encode(payload, settings.JWT_PRIVATE_KEY, algorithm="RS256", headers=headers)


def public_jwk() -> dict[str, Any] | None:
    """Return the current RSA verification key as a JWK dictionary, if configured."""
    if not settings.JWT_PUBLIC_KEY:
        return None
    loaded = load_pem_public_key(settings.JWT_PUBLIC_KEY.encode("utf-8"))
    if not isinstance(loaded, RSAPublicKey):
        raise RuntimeError("JWT_PUBLIC_KEY must be an RSA public key.")
    numbers = loaded.public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": getattr(settings, "JWT_KEY_ID", "core-rs256-v1"),
        "n": _b64url_uint(numbers.n),
        "e": _b64url_uint(numbers.e),
    }


def jwks_body() -> dict[str, list[dict[str, Any]]]:
    """Return an RFC 7517 JWK Set payload."""
    jwk = public_jwk()
    return {"keys": [jwk] if jwk is not None else []}
