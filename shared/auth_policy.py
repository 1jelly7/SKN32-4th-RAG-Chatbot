"""두 HTTP 서비스가 공유하는 역할과 데이터베이스 접근 정책."""

from __future__ import annotations

from typing import Literal

Role = Literal["admin", "hr", "finance"]

SERVICE_DATABASES = frozenset({"document_db", "sales_db", "purchase_db"})
ROLE_DATABASES: dict[Role, frozenset[str]] = {
    "admin": SERVICE_DATABASES,
    "hr": frozenset({"document_db"}),
    "finance": frozenset({"document_db", "sales_db", "purchase_db"}),
}


def allowed_databases(role: Role) -> list[str]:
    """검증된 역할에 허용된 DB 이름을 안정적인 순서로 반환한다."""
    return sorted(ROLE_DATABASES[role])
