from typing import Any

from django.db import models

from common.models import BaseModel


class Ticket(BaseModel):
    """Shared with the validation feature, which adds the later lifecycle states (purchase design N-03)."""

    class Status(models.TextChoices):
        ISSUED = "ISSUED"
        ACTIVE = "ACTIVE"
        USED_UP = "USED_UP"
        EXPIRED = "EXPIRED"
        CANCELLED = "CANCELLED"

    purchase = models.ForeignKey("purchases.Purchase", on_delete=models.PROTECT, related_name="tickets")
    passenger_id = models.UUIDField()  # owned by core-backend; no foreign key across services
    ticket_type = models.ForeignKey("ticket_types.TicketType", on_delete=models.PROTECT, related_name="+")
    terms_snapshot = models.JSONField()  # immutable copy taken at purchase (FR-081)
    price_cents = models.IntegerField()
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ISSUED)
    issued_at = models.DateTimeField()
    remaining_journeys = models.IntegerField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    version = models.IntegerField(default=1)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if (
            self.remaining_journeys is None
            and isinstance(self.terms_snapshot, dict)
            and self.terms_snapshot.get("journeys") is not None
        ):
            self.remaining_journeys = self.terms_snapshot["journeys"]
        super().save(*args, **kwargs)

    class Meta:
        db_table = "tickets"
        constraints = [
            # Backstop for "a confirmed payment ends in exactly one ticket" (PUR-NFR-01).
            models.UniqueConstraint(fields=["purchase"], name="uq_tickets_purchase"),
            models.CheckConstraint(
                condition=models.Q(status__in=["ISSUED", "ACTIVE", "USED_UP", "EXPIRED", "CANCELLED"]),
                name="ck_tickets_status",
            ),
            models.CheckConstraint(
                condition=models.Q(remaining_journeys__isnull=True) | models.Q(remaining_journeys__gte=0),
                name="ck_tickets_remaining_journeys_non_negative",
            ),
        ]


class Validator(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        INACTIVE = "INACTIVE"

    stop_id = models.UUIDField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    code = models.CharField(max_length=64, unique=True)

    class Meta:
        db_table = "validators"


class ValidationAttempt(BaseModel):
    """Append-only history of validation attempts (FR-034, FR-043, FR-047)."""

    class Result(models.TextChoices):
        ACCEPTED = "ACCEPTED"
        REJECTED = "REJECTED"

    class Reason(models.TextChoices):
        UNKNOWN_TICKET = "UNKNOWN_TICKET"
        CANCELLED = "CANCELLED"
        EXPIRED = "EXPIRED"
        NO_JOURNEYS_LEFT = "NO_JOURNEYS_LEFT"

    validator = models.ForeignKey(
        Validator, on_delete=models.PROTECT, related_name="validation_attempts", null=True, blank=True
    )
    stop_id = models.UUIDField(null=True, blank=True)
    idempotency_key = models.UUIDField(null=True, blank=True)
    payload_hash = models.CharField(max_length=64, null=True, blank=True)
    presented_ticket_id = models.UUIDField(null=True, blank=True)
    ticket = models.ForeignKey(
        Ticket, on_delete=models.PROTECT, related_name="validation_attempts", null=True, blank=True
    )
    result = models.CharField(max_length=16, choices=Result.choices)
    reason = models.CharField(max_length=32, choices=Reason.choices, null=True, blank=True)
    decided_at = models.DateTimeField()
    device_time = models.DateTimeField(null=True, blank=True)
    response = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "validation_attempts"
        ordering = ["-decided_at", "-created_at"]


class TicketStateChange(BaseModel):
    """Append-only history of ticket states (FR-035). Database-level UPDATE/DELETE blocking is task T-04, not done yet."""

    class Reason(models.TextChoices):
        PURCHASE = "PURCHASE"
        VALIDATION = "VALIDATION"
        EXPIRY = "EXPIRY"
        CANCELLATION = "CANCELLATION"

    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name="state_changes")
    from_status = models.CharField(max_length=16, null=True, blank=True)
    to_status = models.CharField(max_length=16)
    reason = models.CharField(max_length=32, choices=Reason.choices)
    correlation_id = models.CharField(max_length=128)

    class Meta:
        db_table = "ticket_state_changes"
        ordering = ["-created_at"]
