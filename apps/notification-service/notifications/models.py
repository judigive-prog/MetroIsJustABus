from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import BaseModel
from preferences.models import NotificationChannel


class DeliveryStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    DELIVERED = "DELIVERED", _("Delivered")
    FAILED = "FAILED", _("Failed")


class NotificationRecord(BaseModel):
    """Tracks logical notification issuance and deduplication per (event_id, passenger_id, channel) (FR-066)."""

    event_id = models.UUIDField(db_index=True)
    passenger_id = models.UUIDField(db_index=True)
    channel = models.CharField(max_length=16, choices=NotificationChannel.choices)
    status = models.CharField(max_length=16, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        db_table = "notification_records"
        constraints = (
            models.UniqueConstraint(
                fields=["event_id", "passenger_id", "channel"],
                name="uq_notifications_event_passenger_channel",
            ),
        )

    def __str__(self) -> str:
        return f"NotificationRecord(event={self.event_id}, passenger={self.passenger_id}, channel={self.channel}, status={self.status})"
