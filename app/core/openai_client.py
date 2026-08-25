"""앱 수명주기 동안 OpenAI 비동기 연결 풀을 재사용하는 composition 경계."""

from __future__ import annotations

from typing import Any

_client: Any | None = None


def get_async_openai_client(api_key: str) -> Any:
    """검증된 API key로 단일 AsyncOpenAI client를 지연 생성해 반환한다.

    SDK client는 내부 HTTP keep-alive 연결 풀을 소유하므로 요청마다 새로 만들지 않는다.
    API key 원문이나 client 설정은 로그에 기록하지 않는다.
    """
    if not api_key:
        raise ValueError("OpenAI API key가 비어 있습니다.")
    global _client
    if _client is None:
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(api_key=api_key)
    return _client
