"""Read queries and public representations for accounts (conventions.md, Code)."""

from typing import Any

from accounts.models import AccountProfile, User
from common.clock import to_iso


def find_user_by_email(email: str) -> User | None:
    return User.objects.filter(email=email.strip().lower()).first()


def active_role_for_user(user: User) -> str:
    assignment = user.role_assignments.filter(active=True).order_by("assigned_at").first()
    return assignment.role if assignment is not None else ""


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
