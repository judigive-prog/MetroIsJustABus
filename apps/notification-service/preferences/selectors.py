import uuid

from preferences.models import DEFAULT_CHANGE_TYPES, NotificationChannel, NotificationPreference


def get_preferences_for_passenger(passenger_id: uuid.UUID) -> list[NotificationPreference]:
    existing = {pref.channel: pref for pref in NotificationPreference.objects.filter(passenger_id=passenger_id)}

    result: list[NotificationPreference] = []
    for channel in NotificationChannel.values:
        if channel in existing:
            result.append(existing[channel])
        else:
            result.append(
                NotificationPreference(
                    passenger_id=passenger_id,
                    channel=channel,
                    enabled=True,
                    enabled_change_types=list(DEFAULT_CHANGE_TYPES),
                )
            )
    return result


def is_channel_enabled_for_passenger(
    passenger_id: uuid.UUID,
    channel: str,
    change_type: str,
) -> bool:
    pref = NotificationPreference.objects.filter(passenger_id=passenger_id, channel=channel).first()
    if pref is None:
        # Defaults to True for all supported channels and change types
        return channel in NotificationChannel.values and change_type in DEFAULT_CHANGE_TYPES

    if not pref.enabled:
        return False

    return change_type in pref.enabled_change_types
