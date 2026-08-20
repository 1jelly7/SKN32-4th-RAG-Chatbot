"""기존 accounts와 Django 사용자 이관 결과를 민감정보 없이 대조한다."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from django_app.accounts.models import User


def _normalized_datetime(value: datetime | None, *, legacy: bool) -> str | None:
    """legacy wall clock과 Django aware datetime을 UTC 초 단위로 정규화한다."""
    if value is None:
        return None
    if value.tzinfo is None:
        assumed_zone = ZoneInfo(settings.LEGACY_ACCOUNT_TIME_ZONE if legacy else settings.TIME_ZONE)
        value = value.replace(tzinfo=assumed_zone)
    return value.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0).isoformat()


class Command(BaseCommand):
    """계정 수와 공개 identity·역할·상태·주요 시각의 이관 일치를 확인한다."""

    help = "Audit legacy accounts against migrated Django users without exposing credentials."

    def handle(self, *args: object, **options: object) -> None:
        if "accounts" not in connection.introspection.table_names():
            raise CommandError("Legacy accounts table does not exist.")

        table = connection.ops.quote_name("accounts")
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT id, username, display_name, role, is_active, "
                f"last_login_at, created_at FROM {table}"
            )
            legacy_rows = {int(row[0]): row[1:] for row in cursor.fetchall()}

        migrated = {
            int(user.legacy_account_id): user
            for user in User.objects.exclude(legacy_account_id__isnull=True)
        }
        mismatched_ids: list[int] = []
        for account_id, row in legacy_rows.items():
            user = migrated.get(account_id)
            if user is None:
                mismatched_ids.append(account_id)
                continue
            username, display_name, role, is_active, last_login, created_at = row
            if (
                user.pk != account_id
                or user.username != username
                or user.display_name != display_name
                or user.role != role
                or user.is_active != bool(is_active)
                or _normalized_datetime(user.last_login, legacy=False)
                != _normalized_datetime(last_login, legacy=True)
                or _normalized_datetime(user.date_joined, legacy=False)
                != _normalized_datetime(created_at, legacy=True)
            ):
                mismatched_ids.append(account_id)

        extra_ids = sorted(set(migrated) - set(legacy_rows))
        if mismatched_ids or extra_ids:
            raise CommandError(
                "Legacy account audit failed: "
                f"mismatch_ids={sorted(mismatched_ids)}, extra_migrated_ids={extra_ids}"
            )
        self.stdout.write(
            self.style.SUCCESS(f"Legacy account audit passed: account_count={len(legacy_rows)}")
        )
