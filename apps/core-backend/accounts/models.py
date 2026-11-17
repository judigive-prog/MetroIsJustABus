from django.contrib.auth.hashers import check_password, make_password
from django.db import models

from common.models import BaseModel


class User(BaseModel):
    """Authoritative user identity owned by core-backend (DES-01, NFR-051)."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DISABLED = "DISABLED", "Disabled"

    email = models.EmailField(max_length=254, unique=True)
    password_hash = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        db_table = "users"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["ACTIVE", "DISABLED"]),
                name="ck_users_status",
            ),
            models.CheckConstraint(
                condition=models.Q(password_hash__startswith="argon2$argon2id$"),
                name="ck_users_password_argon2id",
            ),
        ]

    def set_password(self, raw_password: str) -> None:
        if not raw_password or not raw_password.strip():
            raise ValueError("Password must not be empty.")
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        if not raw_password or not self.password_hash:
            return False
        return check_password(raw_password, self.password_hash)

    def __str__(self) -> str:
        return f"User(id={self.id}, status={self.status})"


class AccountProfile(BaseModel):
    """Minimal identity and contact profile separated per DES-01 and A-14."""

    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name="profile")
    full_name = models.CharField(max_length=200)
    contact_email = models.EmailField(max_length=254)
    phone = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        db_table = "account_profiles"

    def __str__(self) -> str:
        return f"AccountProfile(user_id={self.user_id})"


class RoleAssignment(BaseModel):
    """Explicit role assignment supporting visitor/passenger/staff separation (DES-01, FR-100, A-07)."""

    class Role(models.TextChoices):
        PASSENGER = "passenger", "Passenger"
        STAFF = "staff", "Staff"

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="role_assignments")
    role = models.CharField(max_length=16, choices=Role.choices)
    active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "role_assignments"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=["passenger", "staff"]),
                name="ck_role_assignments_role",
            ),
            models.UniqueConstraint(
                fields=["user", "role"],
                condition=models.Q(active=True),
                name="uq_role_assignments_active_user_role",
            ),
        ]

    def __str__(self) -> str:
        return f"RoleAssignment(user_id={self.user_id}, role={self.role}, active={self.active})"
