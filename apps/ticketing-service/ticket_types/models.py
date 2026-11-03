from django.db import models

from common.models import BaseModel


class TicketType(BaseModel):
    """Owned by ticketing. Maintained by staff in another feature (FR-080); seeded for purchase."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        RETIRED = "RETIRED"

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(help_text="Human-readable conditions shown to passengers (FR-031).")
    price_cents = models.IntegerField()
    currency = models.CharField(max_length=3)
    # Validity rules. Their shape is owned by the ticket-type and validation features; purchase copies them opaquely.
    terms = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        db_table = "ticket_types"
        constraints = [
            models.CheckConstraint(condition=models.Q(price_cents__gte=0), name="ck_ticket_types_price_non_negative"),
            models.CheckConstraint(condition=models.Q(currency__regex=r"^[A-Z]{3}$"), name="ck_ticket_types_currency"),
            models.CheckConstraint(condition=models.Q(status__in=["ACTIVE", "RETIRED"]), name="ck_ticket_types_status"),
        ]
