"""한 곳에서 관리하는 역할별 데이터베이스 접근 정책이다."""

from __future__ import annotations

from typing import Literal

Role = Literal["admin", "hr", "finance"]

SERVICE_DATABASES = frozenset({"document_db", "account_db", "sales_db", "purchase_db"})
ROLE_DATABASES: dict[Role, frozenset[str]] = {
    "admin": SERVICE_DATABASES,
    "hr": frozenset({"document_db", "account_db"}),
    "finance": frozenset({"document_db", "sales_db", "purchase_db"}),
}


def allowed_databases(role: Role) -> list[str]:
    """검증된 역할의 허용 DB를 안정적인 순서로 반환한다."""
    return sorted(ROLE_DATABASES[role])


def can_access_database(role: Role, database: str) -> bool:
    """클라이언트 값이 아닌 서버 역할 정책으로 DB 접근을 판정한다."""
    return database in ROLE_DATABASES[role]


def require_database_access(context: dict[str, object] | None, database: str) -> None:
    """MCP/SQL 경계에서 서버가 전달한 컨텍스트의 DB 권한을 강제한다."""
    if context is None or not isinstance(context.get("role"), str):
        raise PermissionError("인증된 사용자 컨텍스트가 필요합니다.")
    role = context["role"]
    if role not in ("admin", "hr", "finance") or not can_access_database(role, database):
        raise PermissionError("요청한 데이터베이스에 접근할 권한이 없습니다.")
