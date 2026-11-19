import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Line",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=200)),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "Active"), ("INACTIVE", "Inactive")],
                        default="ACTIVE",
                        max_length=16,
                    ),
                ),
                ("version", models.PositiveIntegerField(default=1)),
            ],
            options={
                "db_table": "lines",
                "constraints": [
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
                ],
            },
        ),
        migrations.CreateModel(
            name="Stop",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=200)),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "Active"), ("INACTIVE", "Inactive")],
                        default="ACTIVE",
                        max_length=16,
                    ),
                ),
                ("version", models.PositiveIntegerField(default=1)),
            ],
            options={
                "db_table": "stops",
                "constraints": [
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
                ],
            },
        ),
    ]
