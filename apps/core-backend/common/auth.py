"""Verification of RS256 access tokens issued by core-backend (conventions.md: API)."""

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
    session_id: uuid.UUID | None = None
    is_authenticated: bool = True


class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request: Request) -> tuple[AuthenticatedUser, dict[str, Any]] | None:
        header = request.headers.get("Authorization")
        if not header:
            return None
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise AuthenticationFailed()
        if not settings.JWT_PUBLIC_KEY:
            raise AuthenticationFailed()
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key=settings.JWT_PUBLIC_KEY,
                algorithms=["RS256"],
                issuer=settings.JWT_ISSUER,
                options={"require": ["sub", "exp", "jti"], "verify_iss": settings.JWT_ISSUER is not None},
            )
            user_id = uuid.UUID(str(claims["sub"]))
            session_id = uuid.UUID(str(claims["jti"]))
        except (jwt.PyJWTError, ValueError) as exc:
            raise AuthenticationFailed() from exc

        from accounts.models import AuthSession, User
        from common.clock import default_clock

        active = AuthSession.objects.filter(
            id=session_id,
            user_id=user_id,
            revoked_at__isnull=True,
            expires_at__gt=default_clock.now(),
            user__status=User.Status.ACTIVE,
        ).exists()
        if not active:
            raise AuthenticationFailed()

        user = AuthenticatedUser(id=user_id, role=str(claims.get("role", "")), session_id=session_id)
        return user, claims

    def authenticate_header(self, request: Request) -> str:
        return "Bearer"
