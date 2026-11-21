"""Read queries and public representations for accounts (conventions.md, Code)."""

import uuid
from datetime import datetime
from typing import Any

from accounts.models import AccountProfile, AuthSession, User
from common.clock import to_iso


def find_user_by_email(email: str) -> User | None:
    return User.objects.filter(email=email.strip().lower()).first()


def active_role_for_user(user: User) -> str:
    assignment = user.role_assignments.filter(active=True).order_by("assigned_at").first()
    return assignment.role if assignment is not None else ""


def find_active_session(*, session_id: uuid.UUID, user_id: uuid.UUID, now: datetime) -> AuthSession | None:
    return (
        AuthSession.objects.select_related("user", "user__profile")
        .filter(
            id=session_id,
            user_id=user_id,
            revoked_at__isnull=True,
            expires_at__gt=now,
            user__status=User.Status.ACTIVE,
        )
        .first()
    )


def account_body(user: User, *, profile: AccountProfile | None = None, role: str | None = None) -> dict[str, Any]:
    """Public passenger account representation without credential fields."""
    resolved_profile = profile if profile is not None else user.profile
    resolved_role = role if role is not None else active_role_for_user(user)
    return {
        "id": str(user.id),
        "email": user.email,
        "fullName": resolved_profile.full_name,
        "contactEmail": resolved_profile.contact_email,
        "phone": resolved_profile.phone,
        "role": resolved_role,
        "status": user.status,
        "createdAt": to_iso(user.created_at),
    }


def session_body(session: AuthSession) -> dict[str, Any]:
    """Public representation of an authenticated session (FR-021)."""
    return {
        "sessionId": str(session.id),
        "role": session.role,
        "issuedAt": to_iso(session.issued_at),
        "expiresAt": to_iso(session.expires_at),
        "user": account_body(session.user, role=session.role),
    }
