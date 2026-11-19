import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("network", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RoutePattern",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("direction_label", models.CharField(max_length=100)),
                ("revision", models.PositiveIntegerField(default=1)),
                (
                    "status",
                    models.CharField(
                        choices=[("DRAFT", "Draft"), ("PUBLISHED", "Published"), ("RETIRED", "Retired")],
                        default="PUBLISHED",
                        max_length=16,
                    ),
                ),
                (
                    "line",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="route_patterns",
                        to="network.line",
                    ),
                ),
            ],
            options={
                "db_table": "route_patterns",
                "constraints": [
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
                        fields=("line", "direction_label", "revision"),
                        name="uq_route_patterns_line_direction_revision",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(status="PUBLISHED"),
                        fields=("line", "direction_label"),
                        name="uq_route_patterns_published_direction",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="PatternStop",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("position", models.PositiveIntegerField()),
                (
                    "pattern",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="pattern_stops",
                        to="network.routepattern",
                    ),
                ),
                (
                    "stop",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="pattern_stops",
                        to="network.stop",
                    ),
                ),
            ],
            options={
                "db_table": "pattern_stops",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(position__gte=1),
                        name="ck_pattern_stops_position_positive",
                    ),
                    models.UniqueConstraint(
                        fields=("pattern", "position"),
                        name="uq_pattern_stops_pattern_position",
                    ),
                ],
            },
        ),
    ]
