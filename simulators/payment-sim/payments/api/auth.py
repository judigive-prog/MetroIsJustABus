import hmac
from dataclasses import dataclass

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request


@dataclass(frozen=True)
class ServiceCaller:
    is_authenticated: bool = True


class ServiceTokenAuthentication(BaseAuthentication):
    """Shared service token. How service credentials are issued is still open in the tech stack."""

    def authenticate(self, request: Request) -> tuple[ServiceCaller, None] | None:
        header = request.headers.get("Authorization")
        if not header:
            return None
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(token, settings.SERVICE_TOKEN):
            raise AuthenticationFailed()
        return ServiceCaller(), None

    def authenticate_header(self, request: Request) -> str:
        return "Bearer"
