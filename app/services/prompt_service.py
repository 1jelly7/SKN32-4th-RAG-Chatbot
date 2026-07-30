"""
애플리케이션에서 재사용할 Prompt 템플릿을 관리합니다.
"""

# Prompt 템플릿 목록을 상수 딕셔너리로 정의합니다.
PROMPTS: dict[str, str] = {
    "rag_answer": (
        "아래 검색 문맥만 사용하여 질문에 답하세요.\n"
        "답변 마지막에는 사용한 출처 파일명을 표시하세요.\n"
        "문맥에 답이 없다면 '제공된 문서에서 확인할 수 없습니다.'라고 답하세요.\n\n"
        "[검색 문맥]\n{context}\n\n"
        "[질문]\n{question}"
    ),
    "general_assistant": (
        "당신은 FastAPI, OpenAI, MCP 및 RAG를 설명하는 기술 교육 도우미입니다. "
        "한국어로 명확하고 실용적으로 답하세요."
    ),
}


# Prompt 관리 서비스를 정의합니다.
class PromptService:
    """이름으로 Prompt를 조회하고 목록을 제공합니다."""

    # 전체 Prompt 이름 목록을 반환합니다.
    def list_prompts(self) -> list[str]:
        """등록된 Prompt 이름을 반환합니다."""

        # PROMPTS 딕셔너리의 키를 리스트로 변환합니다.
        return list(PROMPTS.keys())

    # 이름으로 Prompt 템플릿을 조회합니다.
    def get_prompt(self, name: str) -> str:
        """지정한 Prompt 템플릿을 반환합니다."""

        # 등록되지 않은 이름이면 KeyError 대신 이해하기 쉬운 오류를 발생시킵니다.
        if name not in PROMPTS:
            raise ValueError(f"등록되지 않은 Prompt입니다: {name}")

        # 요청한 Prompt 문자열을 반환합니다.
        return PROMPTS[name]
