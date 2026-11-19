from collections.abc import MutableMapping
from typing import Any

_SECRET_KEYS = frozenset(
    {
        "authorization",
        "current_password",
        "jwt",
        "new_password",
        "password",
        "password_hash",
        "raw_password",
        "secret",
        "secret_key",
        "token",
    }
)


def redact_secrets(_logger: object, _method: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """structlog processor: never log tokens, secrets or passwords (NFR-051, NFR-056)."""
    for key in list(event_dict):
        if key.lower() in _SECRET_KEYS:
            event_dict[key] = "[redacted]"
    return event_dict
