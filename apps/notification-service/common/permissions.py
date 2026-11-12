from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request

PASSENGER = "passenger"
STAFF = "staff"


class DenyAll(BasePermission):
    """Default permission: every view must declare its own on purpose (conventions.md, Permissions)."""

    def has_permission(self, request: Request, view: Any) -> bool:
        return False


class IsPassenger(BasePermission):
    """Allows authenticated passengers only (FR-100, FR-102, NFR-050)."""

    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", None) == PASSENGER)


class IsStaff(BasePermission):
    """Allows authenticated staff members only (FR-101, NFR-050)."""

    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", None) == STAFF)
