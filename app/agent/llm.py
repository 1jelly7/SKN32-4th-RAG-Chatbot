from __future__ import annotations

from typing import Any


class LLMClient:
    """OpenAI 호출을 감싸는 비동기 어댑터.

    생성자에서는 비밀값을 로그에 남기지 않고 클라이언트와 모델 식별자를 보관한다.
    실제 구현은 테스트에서 대체 가능하도록 SDK 의존성을 이 클래스에 한정한다.
    """
    def __init__(self, api_key: str, model: str) -> None:
        """API 키와 모델을 검증하고 재사용 가능한 SDK 클라이언트를 준비한다."""
        ...

    async def complete(
        self,
        prompt: str,
        context: list[dict[str, Any]],
    ) -> str:
        """프롬프트와 검증된 근거 context만으로 텍스트 완료를 요청한다.

        context의 출처·내용을 메시지에 구조적으로 포함하고, timeout/네트워크/응답 형식
        오류는 호출자가 구분할 수 있는 예외로 변환한다. 키나 전체 민감 근거는 로그에
        기록하지 않으며, 빈 응답은 정상 답변으로 간주하지 않는다.
        """
        ...


async def complete(prompt: str, context: list[dict[str, Any]]) -> str:
    """기본 설정으로 만든 LLMClient에 위임하는 편의 함수다.

    설정 조회와 클라이언트 생성 위치를 한곳에 모으되, 모듈 import 시 외부 호출이나
    비밀값 검증을 수행하지 않는다.
    """
    ...
