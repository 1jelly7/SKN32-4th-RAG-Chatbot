"""account_db와 테스트 대역을 분리하는 계정 저장소 경계다."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

import pymysql
import pymysql.cursors

from app.auth.models import Account
from app.core.db_pool import get_pool


class AccountRepository(Protocol):
    """로그인 계정 조회와 성공 시각 기록만 제공하는 최소 저장소 계약이다."""

    def find_by_username(self, username: str) -> Account | None: ...
    def record_login(self, account_id: int) -> None: ...


class MySQLAccountRepository:
    """account_db 연결 풀에서 연결을 빌려 파라미터화된 로그인 조회만 수행한다."""

    def __init__(self, host: str, port: int, user: str, password: str, database: str) -> None:
        self._pool = get_pool(host, user, password, database, port=port, autocommit=True)

    def find_by_username(self, username: str) -> Account | None:
        connection = self._pool.connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, username, password_hash, display_name, role, is_active FROM accounts WHERE username = %s",
                    (username,),
                )
                row = cursor.fetchone()
        finally:
            connection.close()
        return _account_from_row(row) if row else None

    def record_login(self, account_id: int) -> None:
        connection = self._pool.connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE accounts SET last_login_at = CURRENT_TIMESTAMP WHERE id = %s", (account_id,))
        finally:
            connection.close()


class MemoryAccountRepository:
    """외부 DB 없이 인증 단위 테스트를 수행하는 결정적 계정 저장소다."""

    def __init__(self, accounts: Iterable[Account] = ()) -> None:
        self._accounts = {account.username: account for account in accounts}
        self.login_ids: list[int] = []

    def find_by_username(self, username: str) -> Account | None:
        return self._accounts.get(username)

    def record_login(self, account_id: int) -> None:
        self.login_ids.append(account_id)


class SettingsAccountRepository:
    """설정을 실제 로그인 요청 시점까지 읽지 않는 production 저장소 어댑터다."""

    def __init__(self) -> None:
        self._repository: MySQLAccountRepository | None = None

    def _get(self) -> MySQLAccountRepository:
        if self._repository is None:
            from app.core.config import get_settings
            settings = get_settings()
            self._repository = MySQLAccountRepository(settings.account_db_host, settings.account_db_port,
                                                      settings.account_db_user, settings.account_db_password,
                                                      settings.account_db_name)
        return self._repository

    def find_by_username(self, username: str) -> Account | None:
        return self._get().find_by_username(username)

    def record_login(self, account_id: int) -> None:
        self._get().record_login(account_id)


def _account_from_row(row: dict[str, object]) -> Account:
    """DB 행을 제한된 역할 타입의 계정 모델로 변환한다."""
    role = str(row["role"])
    if role not in ("admin", "hr", "finance"):
        raise ValueError("지원하지 않는 계정 역할입니다.")
    return Account(int(row["id"]), str(row["username"]), str(row["password_hash"]), str(row["display_name"]), role, bool(row["is_active"]))  # type: ignore[arg-type]