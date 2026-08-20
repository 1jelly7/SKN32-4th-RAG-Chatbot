# Generated for Django 5.2. The custom user must remain in the first accounts migration.

from django.contrib.auth.models import UserManager
from django.db import migrations, models
import django.utils.timezone


def preserve_mysql_username_collation(apps, schema_editor) -> None:
    """legacy username의 대소문자 구분 unique 계약을 MySQL에서 보존한다."""
    if schema_editor.connection.vendor != "mysql":
        return
    table = schema_editor.connection.ops.quote_name("accounts_user")
    column = schema_editor.connection.ops.quote_name("username")
    schema_editor.execute(
        f"ALTER TABLE {table} MODIFY {column} VARCHAR(128) "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL"
    )


class Migration(migrations.Migration):
    initial = True

    dependencies = [("auth", "0012_alter_user_first_name_max_length")]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text="Designates that this user has all permissions without explicitly assigning them.",
                        verbose_name="superuser status",
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        help_text="기존 계정과 호환되는 128자 이하의 고유 사용자명입니다.",
                        max_length=128,
                        unique=True,
                    ),
                ),
                ("first_name", models.CharField(blank=True, max_length=150, verbose_name="first name")),
                ("last_name", models.CharField(blank=True, max_length=150, verbose_name="last name")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="email address")),
                (
                    "is_staff",
                    models.BooleanField(
                        default=False,
                        help_text="Designates whether the user can log into this admin site.",
                        verbose_name="staff status",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.",
                        verbose_name="active",
                    ),
                ),
                (
                    "date_joined",
                    models.DateTimeField(default=django.utils.timezone.now, verbose_name="date joined"),
                ),
                ("display_name", models.CharField(max_length=128)),
                (
                    "role",
                    models.CharField(
                        choices=[("admin", "Admin"), ("hr", "HR"), ("finance", "Finance")],
                        max_length=16,
                    ),
                ),
                ("legacy_account_id", models.PositiveBigIntegerField(blank=True, null=True, unique=True)),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.group",
                        verbose_name="groups",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
            options={
                "db_table": "accounts_user",
            },
            managers=[("objects", UserManager())],
        ),
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["role", "is_active"], name="idx_user_role_active"),
        ),
        migrations.RunPython(
            preserve_mysql_username_collation,
            migrations.RunPython.noop,
            atomic=False,
        ),
    ]
