from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import BaseModel


class NotificationChannel(models.TextChoices):
    IN_APP = "IN_APP", _("In-App Inbox")
    EMAIL = "EMAIL", _("Sandboxed Email")


class NotificationPreference(BaseModel):
    """Passenger notification preference per channel and change type (FR-062, ADR A-06)."""

    passenger_id = models.UUIDField(db_index=True)
    channel = models.CharField(max_length=16, choices=NotificationChannel.choices)
    enabled = models.BooleanField(default=True)
    enabled_change_types = models.JSONField(
        default=list,
        help_text="List of change types enabled for this channel, e.g. ['DISRUPTION', 'DELAY', 'SCHEDULE_CHANGE']",
    )

    class Meta:
        db_table = "notification_preferences"
        constraints = (
            models.UniqueConstraint(
                fields=["passenger_id", "channel"],
                name="uq_preferences_passenger_channel",
            ),
        )

    def __str__(self) -> str:
        return f"NotificationPreference({self.passenger_id}, channel={self.channel}, enabled={self.enabled})"
