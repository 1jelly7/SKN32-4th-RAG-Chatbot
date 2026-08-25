"""
프로젝트 전체에서 사용하는 환경설정을 정의합니다.
"""

# 미래 버전의 타입 힌트 평가 방식을 사용합니다.
from __future__ import annotations

# 반복 사용한 설정 객체를 캐시하기 위해 lru_cache를 가져옵니다.
from functools import lru_cache

# 운영체제와 무관하게 파일 경로를 처리하기 위해 Path를 가져옵니다.
from pathlib import Path

# .env 파일과 환경변수를 읽는 BaseSettings를 가져옵니다.
from pydantic_settings import BaseSettings, SettingsConfigDict


# 현재 파일을 기준으로 프로젝트 루트 경로를 계산합니다.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# 프로젝트 환경설정 모델을 정의합니다.
class Settings(BaseSettings):
    """환경변수와 .env 파일의 값을 타입 안전하게 관리합니다."""

    # 애플리케이션 화면과 문서에 표시할 이름을 정의합니다.
    app_name: str = "FastAPI + OpenAI + MCP 기반 RAG Assistant"

    # FastAPI 서버가 사용할 호스트 주소를 정의합니다.
    app_host: str = "127.0.0.1"

    # FastAPI 서버가 사용할 포트 번호를 정의합니다.
    app_port: int = 8000

    # OpenAI API 키를 저장합니다.
    openai_api_key: str = ""

    # OpenAI 질의응답에 사용할 모델 이름을 정의합니다.
    openai_chat_model: str = "gpt-4.1-mini"

    # OpenAI 임베딩에 사용할 모델 이름을 정의합니다.
    openai_embedding_model: str = "text-embedding-3-small"

    # 임베딩 구현을 local, sbert, openai 중에서 선택합니다.
    # local: 외부 다운로드 없는 해시 기반(오프라인, 정확도 낮음)
    # sbert: sentence-transformers 로컬 모델(최초 1회 모델 다운로드 필요, 정확도 높음, API 비용 없음)
    # openai: OpenAI Embeddings API(정확도 가장 높음, API 비용 발생)
    embedding_backend: str = "local"

    # sbert 백엔드를 선택했을 때 사용할 한국어 임베딩 모델입니다.
    sbert_model_name: str = "jhgan/ko-sroberta-multitask"

    # 벡터 저장소 구현을 faiss 또는 qdrant 중에서 선택합니다.
    vector_backend: str = "faiss"

    # Qdrant를 local 또는 server 방식으로 실행할지 정의합니다.
    qdrant_mode: str = "local"

    # 외부 Qdrant 서버 주소를 정의합니다.
    qdrant_url: str = "http://127.0.0.1:6333"

    # Qdrant 컬렉션 이름을 정의합니다.
    qdrant_collection: str = "mcp_rag_documents"

    # MySQL 서버 주소를 정의합니다.
    mysql_host: str = "127.0.0.1"

    # MySQL 서버 포트를 정의합니다.
    mysql_port: int = 3306

    # MySQL 데이터베이스 이름을 정의합니다.
    mysql_database: str = "mcp_rag_db"

    # MySQL 사용자 이름을 정의합니다.
    mysql_user: str = "mcp_user"

    # MySQL 비밀번호를 정의합니다.
    mysql_password: str = "1234"

    # MySQL 기능을 활성화할지 정의합니다.
    mysql_enabled: bool = False

    # RAG가 문서 목록을 어디서 가져올지 선택합니다.
    # filesystem: docs 폴더를 직접 스캔 (기존 방식)
    # mysql: MySQL documents 테이블에 등록된 file_path 목록을 사용 (실무 방식 모방)
    document_source: str = "filesystem"

    # RAG 검색에서 반환할 기본 문서 수를 정의합니다.
    rag_top_k: int = 4

    # 문서를 분할할 때 사용할 최대 문자 수를 정의합니다.
    chunk_size: int = 700

    # 문서 청크 사이에서 겹칠 문자 수를 정의합니다.
    chunk_overlap: int = 100

    # 로컬 임베딩 벡터의 차원을 정의합니다.
    local_embedding_dimension: int = 384

    # 원본 학습 문서가 저장되는 디렉터리를 정의합니다.
    docs_dir: Path = PROJECT_ROOT / "docs"

    # FAISS 인덱스가 저장되는 디렉터리를 정의합니다.
    faiss_dir: Path = PROJECT_ROOT / "data" / "faiss"

    # Qdrant local 데이터가 저장되는 디렉터리를 정의합니다.
    qdrant_dir: Path = PROJECT_ROOT / "data" / "qdrant"

    # .env 파일을 읽고 환경변수 이름의 대소문자를 구분하지 않도록 설정합니다.
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# 설정 객체를 한 번만 생성하여 재사용하도록 캐시합니다.
@lru_cache
def get_settings() -> Settings:
    """프로젝트 전역에서 사용할 Settings 객체를 반환합니다."""

    # Settings 인스턴스를 생성하여 반환합니다.
    return Settings()
