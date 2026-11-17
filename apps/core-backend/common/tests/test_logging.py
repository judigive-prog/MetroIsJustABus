import pytest

from common.logging import redact_secrets


@pytest.mark.unit
@pytest.mark.req("NFR-051")
@pytest.mark.req("NFR-056")
def test_redact_secrets_masks_password_and_hash_keys() -> None:
    event = {
        "event": "user_credentials_created",
        "user_id": "123",
        "password": "canary-plaintext-password",
        "password_hash": "argon2$argon2id$v=19$...",
        "raw_password": "canary-raw-password",
        "token": "canary-jwt-token",
    }

    redacted = redact_secrets(object(), "info", dict(event))

    assert redacted["user_id"] == "123"
    assert redacted["password"] == "[redacted]"
    assert redacted["password_hash"] == "[redacted]"
    assert redacted["raw_password"] == "[redacted]"
    assert redacted["token"] == "[redacted]"
