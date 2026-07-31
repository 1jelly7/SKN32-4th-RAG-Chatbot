from __future__ import annotations

from typing import Any

<<<<<<< HEAD
from app.core.config import get_settings

DEMO_NOTICE = "[로컬 데모 응답] OPENAI_API_KEY가 없어 실제 GPT 응답 대신 근거 요약만 표시합니다.\n\n"

=======
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0

class LLMClient:
    """OpenAI 호출을 감싸는 비동기 어댑터.

<<<<<<< HEAD
    API 키가 없으면 예외를 던지는 대신, 검증된 근거(context)를 그대로 정리해서
    보여주는 데모 모드로 동작한다 - 이 프로젝트 전체에서 일관되게 쓰는 패턴이다.
    """

    def __init__(self, api_key: str, model: str) -> None:
        """API 키와 모델을 검증하고 재사용 가능한 SDK 클라이언트를 준비한다."""
        self._api_key = api_key
        self._model = model
        self._client = None
        if api_key:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=api_key)

    @property
    def is_demo_mode(self) -> bool:
        return self._client is None
=======
    생성자에서는 비밀값을 로그에 남기지 않고 클라이언트와 모델 식별자를 보관한다.
    실제 구현은 테스트에서 대체 가능하도록 SDK 의존성을 이 클래스에 한정한다.
    """
    def __init__(self, api_key: str, model: str) -> None:
        """API 키와 모델을 검증하고 재사용 가능한 SDK 클라이언트를 준비한다."""
        ...
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0

    async def complete(
        self,
        prompt: str,
        context: list[dict[str, Any]],
    ) -> str:
        """프롬프트와 검증된 근거 context만으로 텍스트 완료를 요청한다.

<<<<<<< HEAD
        context의 출처·내용을 메시지에 구조적으로 포함한다. API 키가 없으면
        근거를 그대로 요약해 보여주는 데모 응답으로 대체한다.
        """
        if self._client is None:
            return DEMO_NOTICE + _format_context_as_demo_answer(context)

        context_text = "\n\n".join(
            f"[근거 {i + 1} | {item.get('type', 'unknown')}] {_stringify_evidence(item)}"
            for i, item in enumerate(context)
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"근거:\n{context_text}" if context_text else "근거 없음"},
                ],
                temperature=0.2,
                timeout=30,
            )
        except Exception as exc:  # noqa: BLE001 - 호출자가 구분 가능한 예외로 재발생
            raise RuntimeError(f"LLM 호출에 실패했습니다: {exc}") from exc

        content = response.choices[0].message.content
        if not content or not content.strip():
            raise RuntimeError("LLM이 빈 응답을 반환했습니다.")
        return content.strip()


def _stringify_evidence(item: dict[str, Any]) -> str:
    if item.get("type") == "database":
        rows_preview = item.get("rows", [])[:5]
        return f"SQL: {item.get('generated_sql', '')}\n결과({item.get('row_count', 0)}건 중 일부): {rows_preview}"
    return str(item.get("content", item))


def _format_context_as_demo_answer(context: list[dict[str, Any]]) -> str:
    if not context:
        return "근거를 찾지 못했습니다."
    lines = []
    for i, item in enumerate(context, start=1):
        lines.append(f"{i}. {_stringify_evidence(item)[:300]}")
    return "\n".join(lines)


_default_client: LLMClient | None = None


def _get_default_client() -> LLMClient:
    global _default_client
    if _default_client is None:
        settings = get_settings()
        _default_client = LLMClient(api_key=settings.openai_api_key, model=settings.openai_model)
    return _default_client


async def complete(prompt: str, context: list[dict[str, Any]]) -> str:
    """기본 설정으로 만든 LLMClient에 위임하는 편의 함수다."""
    return await _get_default_client().complete(prompt, context)
=======
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
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0
