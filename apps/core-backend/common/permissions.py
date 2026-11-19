from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.permissions import BasePermission
from rest_framework.request import Request

if TYPE_CHECKING:
    from rest_framework.views import APIView

VISITOR = "visitor"
PASSENGER = "passenger"
STAFF = "staff"
HUMAN_ROLES = frozenset({PASSENGER, STAFF})


class DenyAll(BasePermission):
    """Default permission: every view must declare its own on purpose (conventions.md, Permissions)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return False


class IsAuthenticatedRole(BasePermission):
    """Allows any authenticated human account holding a recognized `passenger` or `staff` role (FR-100)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", None) in HUMAN_ROLES)


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
