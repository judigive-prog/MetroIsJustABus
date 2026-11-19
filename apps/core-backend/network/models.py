from django.db import models

from common.models import BaseModel


class NetworkStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class Line(BaseModel):
    """Published bus line owned by core-backend (DES-01, FR-001)."""

    Status = NetworkStatus

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=16, choices=NetworkStatus.choices, default=NetworkStatus.ACTIVE)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "lines"
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(code=""),
                name="ck_lines_code_non_empty",
            ),
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="ck_lines_name_non_empty",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["ACTIVE", "INACTIVE"]),
                name="ck_lines_status",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1),
                name="ck_lines_version_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"Line(id={self.id}, code={self.code}, status={self.status})"


class Stop(BaseModel):
    """Bus stop shared across lines and patterns (DES-01, FR-001)."""

    Status = NetworkStatus

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=16, choices=NetworkStatus.choices, default=NetworkStatus.ACTIVE)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "stops"
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(code=""),
                name="ck_stops_code_non_empty",
            ),
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="ck_stops_name_non_empty",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["ACTIVE", "INACTIVE"]),
                name="ck_stops_status",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1),
                name="ck_stops_version_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"Stop(id={self.id}, code={self.code}, status={self.status})"
