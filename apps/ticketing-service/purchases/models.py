from django.db import models

from common.models import BaseModel


class Purchase(BaseModel):
    """One purchase request of one ticket (N-02). The row is also the idempotency record (N-10)."""

    class Status(models.TextChoices):
        PENDING = "PENDING"
        COMPLETED = "COMPLETED"
        FAILED = "FAILED"

    passenger_id = models.UUIDField()  # from the verified token; owned by core-backend
    idempotency_key = models.UUIDField()
    request_fingerprint = models.CharField(max_length=64)
    ticket_type = models.ForeignKey("ticket_types.TicketType", on_delete=models.PROTECT, related_name="+")

    # Snapshot frozen at creation (PUR-FR-06).
    terms_snapshot = models.JSONField()
    price_cents = models.IntegerField()
    currency = models.CharField(max_length=3)

    # Kept so the reconciler can replay the payment with the same payload (design §6.3).
    # A simulated opaque token, never real payment data (PUR-NFR-09). Never logged or returned.
    payment_method_token = models.CharField(max_length=64)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    payment_id = models.CharField(max_length=64, null=True, blank=True)
    failure_code = models.CharField(max_length=64, null=True, blank=True)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)  # never contains correlationId

    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    correlation_id = models.CharField(max_length=128)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "purchases"
        constraints = [
            models.UniqueConstraint(fields=["passenger_id", "idempotency_key"], name="uq_purchases_passenger_key"),
            models.CheckConstraint(
                condition=models.Q(status__in=["PENDING", "COMPLETED", "FAILED"]), name="ck_purchases_status"
            ),
            models.CheckConstraint(
                condition=models.Q(status="PENDING") | models.Q(response_status__isnull=False),
                name="ck_purchases_terminal_has_response",
            ),
            models.CheckConstraint(
                condition=~models.Q(status="COMPLETED") | models.Q(payment_id__isnull=False),
                name="ck_purchases_completed_has_payment",
            ),
            models.CheckConstraint(condition=models.Q(price_cents__gte=0), name="ck_purchases_price_non_negative"),
        ]
        indexes = [models.Index(fields=["status", "next_attempt_at"], name="ix_purchases_status_next_attempt")]
