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


class RoutePattern(BaseModel):
    """Ordered directional stop pattern owned by a line (DES-01, FR-002)."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        RETIRED = "RETIRED", "Retired"

    line = models.ForeignKey(Line, on_delete=models.PROTECT, related_name="route_patterns")
    direction_label = models.CharField(max_length=100)
    revision = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PUBLISHED)

    class Meta:
        db_table = "route_patterns"
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(direction_label=""),
                name="ck_route_patterns_direction_non_empty",
            ),
            models.CheckConstraint(
                condition=models.Q(revision__gte=1),
                name="ck_route_patterns_revision_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["DRAFT", "PUBLISHED", "RETIRED"]),
                name="ck_route_patterns_status",
            ),
            models.UniqueConstraint(
                fields=["line", "direction_label", "revision"],
                name="uq_route_patterns_line_direction_revision",
            ),
            models.UniqueConstraint(
                fields=["line", "direction_label"],
                condition=models.Q(status="PUBLISHED"),
                name="uq_route_patterns_published_direction",
            ),
        ]

    def __str__(self) -> str:
        return f"RoutePattern(line_id={self.line_id}, direction={self.direction_label}, rev={self.revision})"


class PatternStop(BaseModel):
    """One ordered stop occurrence inside a route pattern (DES-01, FR-002)."""

    pattern = models.ForeignKey(RoutePattern, on_delete=models.PROTECT, related_name="pattern_stops")
    stop = models.ForeignKey(Stop, on_delete=models.PROTECT, related_name="pattern_stops")
    position = models.PositiveIntegerField()

    class Meta:
        db_table = "pattern_stops"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(position__gte=1),
                name="ck_pattern_stops_position_positive",
            ),
            models.UniqueConstraint(
                fields=["pattern", "position"],
                name="uq_pattern_stops_pattern_position",
            ),
        ]

    def __str__(self) -> str:
        return f"PatternStop(pattern_id={self.pattern_id}, position={self.position}, stop_id={self.stop_id})"
