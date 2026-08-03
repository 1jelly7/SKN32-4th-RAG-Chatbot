"""계정 검증과 서버 계산 사용자 컨텍스트를 조합하는 인증 서비스다."""

from __future__ import annotations

from app.auth.models import Account
from app.auth.passwords import verify_password
from app.auth.policy import allowed_databases
from app.auth.repository import AccountRepository


class AuthenticationService:
    """저장소 조회 결과로만 로그인 성공 여부와 역할 컨텍스트를 결정한다."""

    def __init__(self, repository: AccountRepository) -> None:
        self._repository = repository

    def authenticate(self, username: str, password: str) -> dict[str, object] | None:
        """활성 계정의 해시를 검증하고 민감값 없는 사용자 컨텍스트를 반환한다."""
        account = self._repository.find_by_username(username)
        if account is None or not account.is_active or not verify_password(password, account.password_hash):
            return None
        self._repository.record_login(account.id)
        return user_context(account)


def user_context(account: Account) -> dict[str, object]:
    """클라이언트 입력과 무관한 역할별 최소 사용자 컨텍스트를 만든다."""
    return {"user_id": account.id, "username": account.username, "display_name": account.display_name,
            "role": account.role, "allowed_databases": allowed_databases(account.role)}
