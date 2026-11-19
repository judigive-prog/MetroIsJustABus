from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.permissions import BasePermission
from rest_framework.request import Request

if TYPE_CHECKING:
    from rest_framework.views import APIView

PASSENGER = "passenger"
STAFF = "staff"


class DenyAll(BasePermission):
    """Default permission: every view must declare its own on purpose (conventions.md, Permissions)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return False


class IsPassenger(BasePermission):
    """Allows authenticated passengers only (FR-100, FR-102, NFR-050)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", None) == PASSENGER)


class IsStaff(BasePermission):
    """Allows authenticated operational staff only (FR-100, FR-101, NFR-050, A-07)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", None) == STAFF)
