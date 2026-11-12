from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import BaseModel


class EntityType(models.TextChoices):
    LINE = "LINE", _("Line")
    STOP = "STOP", _("Stop")
    TRIP = "TRIP", _("Trip")


class Subscription(BaseModel):
    """Passenger subscription to a line, stop, or scheduled trip (FR-060, FR-061)."""

    passenger_id = models.UUIDField(db_index=True)
    entity_type = models.CharField(max_length=16, choices=EntityType.choices)
    entity_id = models.CharField(max_length=128, db_index=True)
    active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "subscriptions"
        constraints = (
            models.UniqueConstraint(
                fields=["passenger_id", "entity_type", "entity_id"],
                name="uq_subscriptions_passenger_entity",
            ),
        )

    def __str__(self) -> str:
        return f"Subscription({self.passenger_id}, {self.entity_type}:{self.entity_id}, active={self.active})"
