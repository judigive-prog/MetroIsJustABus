from django.db import models

from common.models import BaseModel


class Ticket(BaseModel):
    """Shared with the validation feature, which adds the later lifecycle states (purchase design N-03)."""

    class Status(models.TextChoices):
        ISSUED = "ISSUED"

    purchase = models.ForeignKey("purchases.Purchase", on_delete=models.PROTECT, related_name="tickets")
    passenger_id = models.UUIDField()  # owned by core-backend; no foreign key across services
    ticket_type = models.ForeignKey("ticket_types.TicketType", on_delete=models.PROTECT, related_name="+")
    terms_snapshot = models.JSONField()  # immutable copy taken at purchase (FR-081)
    price_cents = models.IntegerField()
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ISSUED)
    issued_at = models.DateTimeField()

    class Meta:
        db_table = "tickets"
        constraints = [
            # Backstop for "a confirmed payment ends in exactly one ticket" (PUR-NFR-01).
            models.UniqueConstraint(fields=["purchase"], name="uq_tickets_purchase"),
            models.CheckConstraint(condition=models.Q(status__in=["ISSUED"]), name="ck_tickets_status"),
        ]


class TicketStateChange(BaseModel):
    """Append-only history of ticket states (FR-035). Database-level UPDATE/DELETE blocking is task T-04, not done yet."""

    class Reason(models.TextChoices):
        PURCHASE = "PURCHASE"

    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name="state_changes")
    from_status = models.CharField(max_length=16, null=True, blank=True)
    to_status = models.CharField(max_length=16)
    reason = models.CharField(max_length=32, choices=Reason.choices)
    correlation_id = models.CharField(max_length=128)

    class Meta:
        db_table = "ticket_state_changes"
