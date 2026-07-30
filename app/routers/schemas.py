"""
FastAPI 요청과 응답 검증에 사용하는 Pydantic 모델을 정의합니다.
"""

# Pydantic의 BaseModel과 Field를 가져옵니다.
from pydantic import BaseModel, Field


# 일반 GPT 질문 요청 모델을 정의합니다.
class ChatRequest(BaseModel):
    """일반 GPT 질문 요청입니다."""

    # 비어 있지 않은 질문 문자열을 정의합니다.
    question: str = Field(min_length=1, description="GPT에 전달할 질문")


# 문서 검색 요청 모델을 정의합니다.
class SearchRequest(BaseModel):
    """Vector Search 요청입니다."""

    # 비어 있지 않은 검색어를 정의합니다.
    query: str = Field(min_length=1, description="검색할 질문 또는 키워드")

    # 1에서 20 사이의 검색 결과 개수를 정의합니다.
    top_k: int = Field(default=4, ge=1, le=20)


# RAG 질문 요청 모델을 정의합니다.
class RagRequest(BaseModel):
    """RAG 답변 생성 요청입니다."""

    # 비어 있지 않은 질문을 정의합니다.
    question: str = Field(min_length=1)

    # 검색에 사용할 문서 개수를 정의합니다.
    top_k: int = Field(default=4, ge=1, le=20)


# 파일 읽기 요청 모델을 정의합니다.
class FileReadRequest(BaseModel):
    """문서 파일 읽기 요청입니다."""

    # docs 폴더 안에서 읽을 파일명을 정의합니다.
    filename: str = Field(min_length=1)


# MySQL 데이터 등록 요청 모델을 정의합니다.
class KnowledgeCreateRequest(BaseModel):
    """MySQL 지식 데이터 등록 요청입니다."""

    # 데이터 제목을 정의합니다.
    title: str = Field(min_length=1, max_length=200)

    # 데이터 본문을 정의합니다.
    content: str = Field(min_length=1)
