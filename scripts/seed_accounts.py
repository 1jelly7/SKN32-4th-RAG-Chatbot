"""개발 환경에서 환경 변수 비밀번호를 scrypt 해시로 초기 계정에 주입한다."""

from __future__ import annotations

import sys
from pathlib import Path

# ``python scripts/seed_accounts.py`` 실행 시에도 프로젝트 패키지를 찾게 한다.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pymysql

from app.auth.passwords import hash_password
from app.core.config import get_settings


def main() -> None:
    """ACCOUNT_SEED_* 값을 평문 저장 없이 idempotent 초기 계정으로 반영한다."""
    settings = get_settings()
    accounts = (("admin", "관리자", "admin", settings.account_seed_admin_password),
                ("hr", "인사부", "hr", settings.account_seed_hr_password),
                ("finance", "재무부", "finance", settings.account_seed_finance_password))
    if any(not password for _, _, _, password in accounts):
        raise ValueError("ACCOUNT_SEED_ADMIN_PASSWORD, ACCOUNT_SEED_HR_PASSWORD, ACCOUNT_SEED_FINANCE_PASSWORD가 필요합니다.")
    connection = pymysql.connect(host=settings.account_db_host, port=settings.account_db_port, user=settings.account_db_user,
                                 password=settings.account_db_password, database=settings.account_db_name, charset="utf8mb4", autocommit=True)
    try:
        with connection.cursor() as cursor:
            for username, display_name, role, password in accounts:
                cursor.execute(
                    "INSERT INTO accounts (username, password_hash, display_name, role) VALUES (%s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash), display_name=VALUES(display_name), role=VALUES(role)",
                    (username, hash_password(str(password)), display_name, role),
                )
    finally:
        connection.close()


if __name__ == "__main__":
    main()
