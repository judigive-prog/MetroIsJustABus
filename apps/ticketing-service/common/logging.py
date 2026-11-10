from collections.abc import MutableMapping
from typing import Any

_SECRET_KEYS = frozenset(
    {"authorization", "token", "jwt", "password", "payment_method_token", "paymentmethodtoken"}
)


def redact_secrets(
    _logger: object, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """structlog processor: never log tokens or passwords (NFR-056, PUR-NFR-05)."""
    for key in list(event_dict):
        if key.lower() in _SECRET_KEYS:
            event_dict[key] = "[redacted]"
    return event_dict
