"""Account credential, password hashing and session services (NFR-051, FR-020, FR-021)."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

import structlog
from argon2.exceptions import InvalidHashError
from django.conf import settings
from django.contrib.auth.hashers import check_password, get_hasher, identify_hasher, make_password
from django.db import IntegrityError, transaction

from accounts.exceptions import (
    DuplicateAccountError,
    InvalidAccountDataError,
    InvalidCredentialsError,
    InvalidPasswordError,
)
from accounts.models import AccountProfile, AuthSession, RoleAssignment, User
from accounts.selectors import active_role_for_user
from accounts.tokens import issue_access_token
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
    phone: str = "",
    role: str = RoleAssignment.Role.PASSENGER,
    clock: Clock = default_clock,
) -> User:
    """Persist a new user, profile and role assignment using salted Argon2id password storage (NFR-051)."""
    normalized_email = email.strip().lower()
    normalized_name = full_name.strip()
    if not normalized_email or not normalized_name:
        raise InvalidAccountDataError()
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
                full_name=normalized_name,
                contact_email=normalized_email,
                phone=phone.strip(),
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


@dataclass(frozen=True)
class LoginOutcome:
    user: User
    session: AuthSession
    access_token: str
    expires_in: int


def authenticate_user(*, email: str, raw_password: str, clock: Clock = default_clock) -> LoginOutcome:
    """Authenticate an active account and open a revocable JWT session (FR-021)."""
    normalized_email = email.strip().lower()
    if not normalized_email or not raw_password:
        raise InvalidCredentialsError()

    user = User.objects.select_related("profile").filter(email=normalized_email).first()
    if user is None or user.status != User.Status.ACTIVE:
        raise InvalidCredentialsError()
    if not verify_password(raw_password, user.password_hash):
        raise InvalidCredentialsError()

    role = active_role_for_user(user)
    if not role:
        raise InvalidCredentialsError()

    issued_at = clock.now()
    expires_in = int(settings.JWT_ACCESS_TTL_SECONDS)
    expires_at = issued_at + timedelta(seconds=expires_in)

    session = AuthSession.objects.create(
        user=user,
        role=role,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    access_token = issue_access_token(
        user_id=user.id,
        session_id=session.id,
        role=role,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    logger.info("user_session_started", user_id=str(user.id), session_id=str(session.id), role=role)
    return LoginOutcome(user=user, session=session, access_token=access_token, expires_in=expires_in)


def end_session(*, session_id: uuid.UUID, user_id: uuid.UUID, clock: Clock = default_clock) -> None:
    """Revoke an active authentication session so its token can no longer authenticate (FR-021)."""
    revoked = AuthSession.objects.filter(
        id=session_id,
        user_id=user_id,
        revoked_at__isnull=True,
    ).update(revoked_at=clock.now())
    if revoked:
        logger.info("user_session_ended", user_id=str(user_id), session_id=str(session_id))
