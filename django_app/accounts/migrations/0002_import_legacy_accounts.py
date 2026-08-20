"""기존 FastAPI accounts 행을 보존한 채 Django 사용자로 한 번 이관한다."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import migrations

_LEGACY_SCRYPT_N = 2**14
_LEGACY_SCRYPT_R = 8
_LEGACY_SCRYPT_P = 1
_LEGACY_SCRYPT_SALT_LENGTH = 16
_LEGACY_SCRYPT_KEY_LENGTH = 32


def _legacy_datetime(value: datetime | None) -> datetime | None:
    """legacy DATETIME을 명시된 기존 DB 시간대의 시각으로 해석한다."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=ZoneInfo(settings.LEGACY_ACCOUNT_TIME_ZONE))


def _validate_legacy_password_hash(encoded: object, account_id: object) -> str:
    """지원하는 고정 scrypt 형식만 이관해 로그인 시 과도한 파라미터 사용을 막는다."""
    try:
        if not isinstance(encoded, str) or len(encoded) > 128:
            raise ValueError
        algorithm, n, r, p, salt, expected, length = encoded.split("$")
        salt_bytes = base64.b64decode(salt, validate=True)
        expected_bytes = base64.b64decode(expected, validate=True)
        if (
            algorithm != "scrypt"
            or int(n) != _LEGACY_SCRYPT_N
            or int(r) != _LEGACY_SCRYPT_R
            or int(p) != _LEGACY_SCRYPT_P
            or int(length) != _LEGACY_SCRYPT_KEY_LENGTH
            or len(salt_bytes) != _LEGACY_SCRYPT_SALT_LENGTH
            or len(expected_bytes) != _LEGACY_SCRYPT_KEY_LENGTH
        ):
            raise ValueError
    except (ValueError, TypeError, binascii.Error):
        raise RuntimeError(
            f"Unsupported legacy password hash for account id {account_id}"
        ) from None
    return encoded


def import_legacy_accounts(apps, schema_editor) -> None:
    """기존 테이블이 있을 때 PK·역할·해시·활성 상태를 새 사용자에 복사한다."""
    connection = schema_editor.connection
    if "accounts" not in connection.introspection.table_names():
        return

    User = apps.get_model("accounts", "User")
    table = connection.ops.quote_name("accounts")
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT id, username, password_hash, display_name, role, is_active, "
            f"last_login_at, created_at FROM {table}"
        )
        rows = cursor.fetchall()

    users = []
    for account_id, username, password_hash, display_name, role, is_active, last_login, created_at in rows:
        if type(account_id) is not int or account_id < 1:
            raise RuntimeError("Legacy account id must be a positive integer")
        if not isinstance(username, str) or not username or len(username) > 128:
            raise RuntimeError(f"Unsupported legacy username for account id {account_id}")
        if not isinstance(display_name, str) or len(display_name) > 128:
            raise RuntimeError(f"Unsupported legacy display name for account id {account_id}")
        if role not in {"admin", "hr", "finance"}:
            raise RuntimeError(f"Unsupported legacy account role for account id {account_id}")
        if is_active not in (False, True, 0, 1):
            raise RuntimeError(f"Unsupported legacy active state for account id {account_id}")
        if last_login is not None and not isinstance(last_login, datetime):
            raise RuntimeError(f"Unsupported legacy login timestamp for account id {account_id}")
        if not isinstance(created_at, datetime):
            raise RuntimeError(f"Unsupported legacy creation timestamp for account id {account_id}")
        users.append(
            User(
                id=account_id,
                legacy_account_id=account_id,
                username=username,
                password=_validate_legacy_password_hash(password_hash, account_id),
                display_name=display_name,
                role=role,
                is_active=bool(is_active),
                is_staff=False,
                is_superuser=False,
                last_login=_legacy_datetime(last_login),
                date_joined=_legacy_datetime(created_at),
            )
        )
    User.objects.bulk_create(users, ignore_conflicts=False)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [migrations.RunPython(import_legacy_accounts)]
