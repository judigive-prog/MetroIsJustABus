import datetime
import uuid

from django.db.models import Q

from preferences.models import DEFAULT_CHANGE_TYPES, NotificationChannel, NotificationPreference, PreferenceHistory


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
    at_time: datetime.datetime | None = None,
) -> bool:
    """Check if a channel and change_type are enabled for a passenger, optionally at event time (FR-062, FR-068)."""
    if at_time is not None:
        history = (
            PreferenceHistory.objects.filter(
                passenger_id=passenger_id,
                channel=channel,
                valid_from__lte=at_time,
            )
            .filter(Q(valid_to__isnull=True) | Q(valid_to__gt=at_time))
            .first()
        )
        if history is not None:
            if not history.enabled:
                return False
            return change_type in history.enabled_change_types

        # If no history covers at_time, check if current pref existed at at_time
        pref = NotificationPreference.objects.filter(passenger_id=passenger_id, channel=channel).first()
        if pref is not None and pref.created_at <= at_time:
            if not pref.enabled:
                return False
            return change_type in pref.enabled_change_types

        # Otherwise defaults apply at event time
        return channel in NotificationChannel.values and change_type in DEFAULT_CHANGE_TYPES

    pref = NotificationPreference.objects.filter(passenger_id=passenger_id, channel=channel).first()
    if pref is None:
        # Defaults to True for all supported channels and change types
        return channel in NotificationChannel.values and change_type in DEFAULT_CHANGE_TYPES

    if not pref.enabled:
        return False

    return change_type in pref.enabled_change_types
