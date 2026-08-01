from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import get_settings

DEMO_NOTICE = "[로컬 데모 응답] OPENAI_API_KEY가 없어 실제 GPT 응답 대신 근거 요약만 표시합니다.\n\n"
SENSITIVE_KEY_PARTS = ("api_key", "password", "secret", "token", "file_path")


class AsyncLLMPort(Protocol):
    """검증된 근거만 사용해 답변을 완성하는 비동기 LLM 경계다."""

    async def complete(self, prompt: str, context: list[dict[str, Any]]) -> str:
        """프롬프트와 안전하게 정규화된 근거로 답변을 생성한다."""
        ...


@dataclass(frozen=True)
class LLMCall:
    """Fake LLM이 기록하는 한 번의 답변 호출이다."""

    prompt: str
    context: list[dict[str, Any]]


class FakeLLMPort:
    """외부 호출 없이 고정 응답과 호출 이력을 제공하는 LLM 대역이다."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.calls: list[LLMCall] = []

    async def complete(self, prompt: str, context: list[dict[str, Any]]) -> str:
        self.calls.append(LLMCall(prompt=prompt, context=deepcopy(context)))
        return self._response


class LLMClient:
    """OpenAI 호출을 감싸는 비동기 어댑터다."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client = None
        if api_key:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=api_key)

    @property
    def is_demo_mode(self) -> bool:
        return self._client is None

    async def complete(self, prompt: str, context: list[dict[str, Any]]) -> str:
        """프롬프트와 검증·정규화된 근거로 텍스트 완료를 요청한다."""
        if self._client is None:
            return DEMO_NOTICE + _format_context_as_demo_answer(context)

        context_text = "\n\n".join(
            f"[근거 {index + 1} | {item.get('type', 'unknown')}] {_stringify_evidence(item)}"
            for index, item in enumerate(context)
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
        except Exception as exc:  # noqa: BLE001 - 외부 SDK 오류 세부값을 사용자·로그에 노출하지 않음
            raise RuntimeError("LLM 호출에 실패했습니다.") from exc

        content = response.choices[0].message.content
        if not content or not content.strip():
            raise RuntimeError("LLM이 빈 응답을 반환했습니다.")
        return content.strip()


def sanitize_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """내부 경로와 비밀값 후보를 제거한 방어적 근거 사본을 반환한다."""
    return [_sanitize_value(item) for item in evidence]


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize_value(item)
            for key, item in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _is_sensitive_key(key: object) -> bool:
    return isinstance(key, str) and any(part in key.casefold() for part in SENSITIVE_KEY_PARTS)


def _stringify_evidence(item: dict[str, Any]) -> str:
    if item.get("type") == "database":
        rows_preview = item.get("rows", [])[:5]
        return f"SQL: {item.get('generated_sql', '')}\n결과({item.get('row_count', 0)}건 중 일부): {rows_preview}"
    return str(item.get("content", item))


def _format_context_as_demo_answer(context: list[dict[str, Any]]) -> str:
    if not context:
        return "근거를 찾지 못했습니다."
    return "\n".join(
        f"{index}. {_stringify_evidence(item)[:300]}"
        for index, item in enumerate(context, start=1)
    )


_default_client: LLMClient | None = None


def _get_default_client() -> LLMClient:
    global _default_client
    if _default_client is None:
        settings = get_settings()
        _default_client = LLMClient(api_key=settings.openai_api_key, model=settings.openai_model)
    return _default_client


async def complete(
    prompt: str,
    context: list[dict[str, Any]],
    llm: AsyncLLMPort | None = None,
) -> str:
    """주입된 LLM 또는 기본 client에 안전한 근거 사본을 전달한다."""
    return await (llm or _get_default_client()).complete(prompt, sanitize_evidence(context))
