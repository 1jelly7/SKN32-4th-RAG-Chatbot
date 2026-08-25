"""한 곳에서 관리하는 역할별 데이터베이스 접근 정책이다."""

from __future__ import annotations

from shared.auth_policy import ROLE_DATABASES, Role, allowed_databases


def can_access_database(role: Role, database: str) -> bool:
    """클라이언트 값이 아닌 서버 역할 정책으로 DB 접근을 판정한다."""
    return database in ROLE_DATABASES[role]


def require_database_access(context: dict[str, object] | None, database: str) -> None:
    """MCP/SQL 경계에서 서버가 전달한 컨텍스트의 DB 권한을 강제한다."""
    if context is None or not isinstance(context.get("role"), str):
        raise PermissionError("인증된 사용자 컨텍스트가 필요합니다.")
    role = context["role"]
    if role not in ("admin", "hr", "finance") or not can_access_database(
        role, database
    ):
        raise PermissionError("요청한 데이터베이스에 접근할 권한이 없습니다.")
