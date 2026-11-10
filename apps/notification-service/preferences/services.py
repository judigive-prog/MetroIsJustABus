import uuid
from typing import Any

import structlog
from django.db import transaction

from preferences.exceptions import InvalidChangeType, InvalidChannel
from preferences.models import ChangeType, NotificationChannel, NotificationPreference

logger = structlog.get_logger(__name__)


def set_preference(
    passenger_id: uuid.UUID,
    channel: str,
    enabled: bool,
    enabled_change_types: list[str],
) -> NotificationPreference:
    if channel not in NotificationChannel.values:
        raise InvalidChannel()

    valid_types = set(ChangeType.values)
    for ct in enabled_change_types:
        if ct not in valid_types:
            raise InvalidChangeType()

    cleaned_change_types = sorted(list(set(enabled_change_types)))

    pref, created = NotificationPreference.objects.update_or_create(
        passenger_id=passenger_id,
        channel=channel,
        defaults={
            "enabled": enabled,
            "enabled_change_types": cleaned_change_types,
        },
    )

    logger.info(
        "notification_preference_saved",
        passenger_id=str(passenger_id),
        channel=channel,
        enabled=enabled,
        created=created,
        change_types=cleaned_change_types,
    )
    return pref


def set_bulk_preferences(
    passenger_id: uuid.UUID,
    items: list[dict[str, Any]],
) -> list[NotificationPreference]:
    with transaction.atomic():
        return [
            set_preference(
                passenger_id=passenger_id,
                channel=item["channel"],
                enabled=item["enabled"],
                enabled_change_types=item.get("enabledChangeTypes", []),
            )
            for item in items
        ]
