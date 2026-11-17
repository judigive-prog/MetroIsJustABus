import base64
from datetime import UTC, datetime

import pytest
from django.conf import settings
from django.contrib.auth.hashers import get_hasher, identify_hasher
from django.core.management import call_command
from django.db import IntegrityError

from accounts.exceptions import InvalidPasswordError
from accounts.hashers import CoreArgon2PasswordHasher
from accounts.models import AccountProfile, RoleAssignment, User
from accounts.services import create_user_credentials, hash_password, password_needs_rehash, verify_password

_WEAK_SALT = base64.b64encode(b"0" * 16).decode("ascii").rstrip("=")
_WEAK_DIGEST = base64.b64encode(b"1" * 32).decode("ascii").rstrip("=")
_WEAK_ARGON2ID_HASH = f"argon2$argon2id$v=19$m=4096,t=1,p=1${_WEAK_SALT}${_WEAK_DIGEST}"


class _FixedClock:
    def __init__(self, instant: datetime) -> None:
        self._instant = instant

    def now(self) -> datetime:
        return self._instant


@pytest.mark.unit
@pytest.mark.req("NFR-051")
def test_only_argon2id_password_hasher_is_configured_with_documented_cost_parameters() -> None:
    assert settings.PASSWORD_HASHERS == ["accounts.hashers.CoreArgon2PasswordHasher"]
    hasher = get_hasher()
    assert isinstance(hasher, CoreArgon2PasswordHasher)
    assert hasher.algorithm == "argon2"
    assert hasher.time_cost == 2
    assert hasher.memory_cost == 19456
    assert hasher.parallelism == 1


@pytest.mark.unit
@pytest.mark.req("NFR-051")
def test_hash_password_produces_salted_argon2id_with_unique_salts() -> None:
    raw = "correct-horse-battery-staple"

    first = hash_password(raw)
    second = hash_password(raw)

    assert raw not in first
    assert raw not in second
    assert first.startswith("argon2$argon2id$v=19$m=19456,t=2,p=1$")
    assert second.startswith("argon2$argon2id$v=19$m=19456,t=2,p=1$")
    assert first != second
    assert first.split("$")[4] != second.split("$")[4]
    assert isinstance(identify_hasher(first), CoreArgon2PasswordHasher)
    assert verify_password(raw, first) is True
    assert verify_password(raw, second) is True
    assert verify_password("wrong-password", first) is False
    assert verify_password("", first) is False
    assert password_needs_rehash(first) is False
    assert password_needs_rehash("pbkdf2_sha256$870000$salt$hash") is True


@pytest.mark.unit
@pytest.mark.req("NFR-051")
@pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
def test_hash_password_rejects_empty_passwords(raw: str) -> None:
    with pytest.raises(InvalidPasswordError):
        hash_password(raw)


@pytest.mark.unit
@pytest.mark.req("NFR-051")
@pytest.mark.parametrize(
    "encoded_hash",
    [
        "",
        "plaintext-password",
        "pbkdf2_sha256$870000$salt$hash",
        "argon2$argon2i$v=19$m=19456,t=2,p=1$c2FsdHNhbHRzYWx0$aGFzaA",
        "argon2$argon2id$corrupt",
        _WEAK_ARGON2ID_HASH,
    ],
)
def test_password_needs_rehash_flags_weak_or_non_argon2id_hashes(encoded_hash: str) -> None:
    assert password_needs_rehash(encoded_hash) is True


@pytest.mark.django_db
@pytest.mark.req("NFR-051")
def test_create_user_credentials_stores_only_salted_argon2id_hash() -> None:
    now = datetime(2026, 11, 17, 23, 0, 0, tzinfo=UTC)
    canary_password = "canary-plaintext-secret-999"

    user = create_user_credentials(
        email="Passenger@Example.com",
        raw_password=canary_password,
        full_name="Alice Silva",
        clock=_FixedClock(now),
    )

    stored = User.objects.get(id=user.id)
    assert stored.email == "passenger@example.com"
    assert stored.password_hash.startswith("argon2$argon2id$")
    assert canary_password not in stored.password_hash
    assert canary_password not in str(stored)
    assert stored.check_password(canary_password) is True
    assert stored.check_password("not-the-password") is False

    profile = AccountProfile.objects.get(user=stored)
    assert profile.full_name == "Alice Silva"
    assert profile.contact_email == "passenger@example.com"

    assignment = RoleAssignment.objects.get(user=stored)
    assert assignment.role == RoleAssignment.Role.PASSENGER
    assert assignment.active is True
    assert assignment.assigned_at == now


@pytest.mark.django_db
@pytest.mark.req("NFR-051")
@pytest.mark.parametrize(
    "invalid_hash",
    [
        "plaintext-password",
        "pbkdf2_sha256$870000$some-salt$some-digest",
        "$argon2id$missing-django-prefix",
    ],
)
def test_database_constraint_rejects_non_argon2id_hashes(invalid_hash: str) -> None:
    with pytest.raises(IntegrityError):
        User.objects.create(email="unsafe@example.com", password_hash=invalid_hash)


@pytest.mark.django_db
@pytest.mark.req("NFR-051")
@pytest.mark.req("NFR-088")
def test_accounts_migrations_are_in_sync_with_models() -> None:
    call_command("makemigrations", "accounts", check=True, dry_run=True)
