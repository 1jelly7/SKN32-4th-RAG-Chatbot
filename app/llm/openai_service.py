"""
OpenAI GPT를 호출하여 일반 질의응답과 RAG 답변을 생성합니다.
"""

# 미래 타입 힌트 평가 방식을 사용합니다.
from __future__ import annotations

# OpenAI Responses API 클라이언트를 가져옵니다.
from openai import OpenAI

# 프로젝트 설정 모델을 가져옵니다.
from app.config.settings import Settings


# OpenAI GPT 호출 기능을 담당하는 클래스를 정의합니다.
class OpenAIService:
    """OpenAI API 호출과 로컬 대체 응답을 제공합니다."""

    # 설정 객체를 전달받아 서비스를 초기화합니다.
    def __init__(self, settings: Settings) -> None:
        # 전달받은 설정을 저장합니다.
        self.settings = settings

        # API 키가 있을 때만 OpenAI 클라이언트를 생성합니다.
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    # 일반 질문에 대한 답변을 생성합니다.
    def answer(self, question: str, system_prompt: str) -> str:
        """OpenAI GPT를 사용하여 일반 질문에 답합니다."""

        # API 키가 없으면 프로젝트 구조를 확인할 수 있는 대체 응답을 반환합니다.
        if self.client is None:
            return (
                "[로컬 데모 응답]\n"
                "OPENAI_API_KEY가 설정되지 않아 실제 GPT 호출은 생략했습니다.\n"
                f"질문: {question}"
            )

        # Responses API에 시스템 지시와 사용자 질문을 전달합니다.
        response = self.client.responses.create(
            model=self.settings.openai_chat_model,
            instructions=system_prompt,
            input=question,
        )

        # 편리한 output_text 속성에서 최종 답변 문자열을 반환합니다.
        return response.output_text

    # 검색 문맥을 근거로 RAG 답변을 생성합니다.
    def answer_with_context(self, question: str, context: str, prompt_template: str) -> str:
        """검색된 문서를 근거로 답변을 생성합니다."""

        # Prompt 템플릿에 검색 문맥과 사용자 질문을 삽입합니다.
        final_prompt = prompt_template.format(context=context, question=question)

        # API 키가 없으면 검색된 문맥을 확인할 수 있는 로컬 응답을 반환합니다.
        if self.client is None:
            return (
                "[로컬 RAG 데모 응답]\n"
                "검색은 정상 수행되었지만 OPENAI_API_KEY가 없어 GPT 생성은 생략했습니다.\n\n"
                f"질문: {question}\n\n"
                f"검색 문맥:\n{context}"
            )

        # OpenAI Responses API에 근거 제한 지시와 완성된 Prompt를 전달합니다.
        response = self.client.responses.create(
            model=self.settings.openai_chat_model,
            instructions=(
                "당신은 근거 중심 RAG Assistant입니다. "
                "제공된 검색 문맥에 없는 사실은 추측하지 말고 모른다고 답하세요."
            ),
            input=final_prompt,
        )

        # 생성된 최종 텍스트를 반환합니다.
        return response.output_text
