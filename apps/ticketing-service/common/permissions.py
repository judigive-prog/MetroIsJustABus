from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

PASSENGER = "passenger"


class DenyAll(BasePermission):
    """Default permission: every view must declare its own on purpose."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return False


class IsPassenger(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", None) == PASSENGER)
