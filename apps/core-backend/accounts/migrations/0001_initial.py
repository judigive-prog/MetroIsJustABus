import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("password_hash", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "Active"), ("DISABLED", "Disabled")],
                        default="ACTIVE",
                        max_length=16,
                    ),
                ),
            ],
            options={
                "db_table": "users",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(status__in=["ACTIVE", "DISABLED"]),
                        name="ck_users_status",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(password_hash__startswith="argon2$argon2id$"),
                        name="ck_users_password_argon2id",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="AccountProfile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("full_name", models.CharField(max_length=200)),
                ("contact_email", models.EmailField(max_length=254)),
                ("phone", models.CharField(blank=True, default="", max_length=32)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="profile",
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "db_table": "account_profiles",
            },
        ),
        migrations.CreateModel(
            name="RoleAssignment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "role",
                    models.CharField(
                        choices=[("passenger", "Passenger"), ("staff", "Staff")],
                        max_length=16,
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                ("assigned_at", models.DateTimeField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="role_assignments",
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "db_table": "role_assignments",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(role__in=["passenger", "staff"]),
                        name="ck_role_assignments_role",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(active=True),
                        fields=("user", "role"),
                        name="uq_role_assignments_active_user_role",
                    ),
                ],
            },
        ),
    ]
