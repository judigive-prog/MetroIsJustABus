import uuid

from django.db import models


class Payment(models.Model):
    """One simulated payment per idempotency key (= ticketing purchase id, N-05)."""

    class Status(models.TextChoices):
        APPROVED = "APPROVED"
        DECLINED = "DECLINED"
        # sim_error: the first call failed with 500 and charged nothing; the next call approves.
        ERRORED = "ERRORED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.UUIDField()
    request_fingerprint = models.CharField(max_length=64)
    amount_cents = models.IntegerField()
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=16, choices=Status.choices)
    reason = models.CharField(max_length=64, null=True, blank=True)
    charge_count = models.PositiveIntegerField(default=0)
    request_count = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments"
        constraints = [
            models.UniqueConstraint(fields=["idempotency_key"], name="uq_payments_idempotency_key"),
            models.CheckConstraint(condition=models.Q(charge_count__lte=1), name="ck_payments_single_charge"),
        ]
