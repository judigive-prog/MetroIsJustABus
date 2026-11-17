"""Account credential and password hashing services (NFR-051)."""

import structlog
from argon2.exceptions import InvalidHashError
from django.contrib.auth.hashers import check_password, get_hasher, identify_hasher, make_password
from django.db import IntegrityError, transaction

from accounts.exceptions import DuplicateAccountError, InvalidPasswordError
from accounts.models import AccountProfile, RoleAssignment, User
from common.clock import Clock, default_clock

logger = structlog.get_logger(__name__)

_ARGON2ID_PREFIX = "argon2$argon2id$"


def hash_password(raw_password: str) -> str:
    """Hash a raw password with the configured salted Argon2id hasher (NFR-051)."""
    if not raw_password or not raw_password.strip():
        raise InvalidPasswordError()
    encoded = make_password(raw_password)
    if not encoded.startswith(_ARGON2ID_PREFIX):
        raise RuntimeError("Configured password hasher did not produce an Argon2id hash.")
    return encoded


def verify_password(raw_password: str, encoded_hash: str) -> bool:
    """Verify a raw password against a stored salted hash (NFR-051)."""
    if not raw_password or not encoded_hash or not encoded_hash.startswith(_ARGON2ID_PREFIX):
        return False
    return check_password(raw_password, encoded_hash)


def password_needs_rehash(encoded_hash: str) -> bool:
    """Return True if an existing stored hash does not match current Argon2id parameters."""
    if not encoded_hash or not encoded_hash.startswith(_ARGON2ID_PREFIX):
        return True
    preferred = get_hasher()
    try:
        current = identify_hasher(encoded_hash)
    except ValueError:
        return True
    if type(current) is not type(preferred):
        return True
    try:
        return preferred.must_update(encoded_hash)
    except (InvalidHashError, ValueError):
        return True


def create_user_credentials(
    *,
    email: str,
    raw_password: str,
    full_name: str,
    role: str = RoleAssignment.Role.PASSENGER,
    clock: Clock = default_clock,
) -> User:
    """Persist a new user, profile and role assignment using salted Argon2id password storage (NFR-051)."""
    normalized_email = email.strip().lower()
    encoded_hash = hash_password(raw_password)
    now = clock.now()

    try:
        with transaction.atomic():
            user = User.objects.create(
                email=normalized_email,
                password_hash=encoded_hash,
                status=User.Status.ACTIVE,
            )
            AccountProfile.objects.create(
                user=user,
                full_name=full_name.strip(),
                contact_email=normalized_email,
            )
            RoleAssignment.objects.create(
                user=user,
                role=role,
                active=True,
                assigned_at=now,
            )
    except IntegrityError as exc:
        raise DuplicateAccountError() from exc

    logger.info("user_credentials_created", user_id=str(user.id), role=role)
    return user
