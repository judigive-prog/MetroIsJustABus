from django.db import models

from common.models import BaseModel


class OutboxEvent(BaseModel):
    """Events waiting to be published by the relay (conventions.md, Events). The relay is not part of this slice."""

    class Status(models.TextChoices):
        PENDING = "PENDING"
        PUBLISHED = "PUBLISHED"

    event_id = models.UUIDField(unique=True)
    event_type = models.CharField(max_length=100)
    routing_key = models.CharField(max_length=200)
    body = models.JSONField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "outbox_event"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["PENDING", "PUBLISHED"]),
                name="ck_outbox_event_status",
            ),
        ]
        indexes = [models.Index(fields=["status", "created_at"], name="ix_outbox_event_status_created")]
