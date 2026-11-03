"""Verification of tokens issued by core-backend.

Assumption (purchase design §10): the JWT carries `sub` (user UUID) and `role`. Not yet confirmed
against core-backend. The public key comes from a file; fetching JWKS with a cache (N-13, OQ-06)
is not implemented.
"""

import uuid
from dataclasses import dataclass
from typing import Any

import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request


@dataclass(frozen=True)
class AuthenticatedUser:
    id: uuid.UUID
    role: str
    is_authenticated: bool = True


class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request: Request) -> tuple[AuthenticatedUser, dict[str, Any]] | None:
        header = request.headers.get("Authorization")
        if not header:
            return None
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise AuthenticationFailed()
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key=settings.JWT_PUBLIC_KEY,
                algorithms=["RS256"],
                issuer=settings.JWT_ISSUER,
                options={"require": ["sub", "exp"], "verify_iss": settings.JWT_ISSUER is not None},
            )
            user = AuthenticatedUser(id=uuid.UUID(str(claims["sub"])), role=str(claims.get("role", "")))
        except (jwt.PyJWTError, ValueError) as exc:
            raise AuthenticationFailed() from exc
        return user, claims

    def authenticate_header(self, request: Request) -> str:
        return "Bearer"
