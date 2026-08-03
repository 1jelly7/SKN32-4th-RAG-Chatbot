"""로그아웃 뒤 이전 서명 세션을 무효화하기 위한 서버 측 세션 레지스트리."""

from __future__ import annotations


class SessionStore:
    """현재 앱 프로세스에서 발급·폐기한 세션 식별자를 관리한다.

    서명과 만료 시각만으로는 이미 발급된 토큰을 로그아웃 직후 폐기할 수 없으므로,
    보호 API는 이 저장소에 활성으로 등록된 세션만 허용한다. 다중 워커 배포에서는
    같은 계약을 공유 저장소 구현으로 교체해야 한다.
    """

    def __init__(self) -> None:
        self._active_session_ids: set[str] = set()

    def issue(self, session_id: str) -> None:
        """새로 발급한 세션 식별자를 활성 상태로 등록한다."""
        self._active_session_ids.add(session_id)

    def revoke(self, session_id: str) -> None:
        """로그아웃한 세션 식별자를 제거해 이후 토큰 재사용을 막는다."""
        self._active_session_ids.discard(session_id)

    def is_active(self, session_id: str) -> bool:
        """보호 API 호출 시 세션이 아직 활성인지 확인한다."""
        return session_id in self._active_session_ids
