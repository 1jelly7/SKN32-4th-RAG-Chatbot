"""비동기 호출 체인 전체에 안전한 요청 상관관계 ID를 전달한다."""

from __future__ import annotations

from contextvars import ContextVar, Token

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str) -> Token[str | None]:
    """현재 비동기 컨텍스트에 request ID를 설정한다."""
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """요청 종료 뒤 이전 컨텍스트 값으로 복원한다."""
    _request_id.reset(token)


def get_request_id() -> str | None:
    """현재 요청의 상관관계 ID를 반환한다."""
    return _request_id.get()
