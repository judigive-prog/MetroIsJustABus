from django.db import models

from common.models import BaseModel


class InboxEvent(BaseModel):
    """Event inbox table for deduplicating consumed messages from RabbitMQ (conventions.md, Events)."""

    event_id = models.UUIDField(unique=True)
    event_type = models.CharField(max_length=128)
    producer = models.CharField(max_length=64)
    correlation_id = models.CharField(max_length=128)
    payload = models.JSONField()
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inbox_event"

    def __str__(self) -> str:
        return f"InboxEvent({self.event_id}, type={self.event_type})"


class InboxNotification(BaseModel):
    """In-app passenger notification inbox item (FR-067, FR-102)."""

    passenger_id = models.UUIDField(db_index=True)
    event_id = models.UUIDField(db_index=True)
    title = models.CharField(max_length=255)
    body = models.TextField()
    change_type = models.CharField(max_length=64)
    entity_type = models.CharField(max_length=32, blank=True, default="")
    entity_id = models.CharField(max_length=128, blank=True, default="")
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "inbox_notifications"
        ordering = ("-created_at",)
        constraints = (
            models.UniqueConstraint(
                fields=["passenger_id", "event_id"],
                name="uq_inbox_notifications_passenger_event",
            ),
        )

    def __str__(self) -> str:
        return f"InboxNotification({self.passenger_id}, event={self.event_id}, title={self.title})"
