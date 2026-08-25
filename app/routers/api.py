"""
프로젝트의 FastAPI REST API 엔드포인트를 정의합니다.
"""

# FastAPI Router와 HTTPException을 가져옵니다.
from fastapi import APIRouter, HTTPException

# 요청 데이터 모델을 가져옵니다.
from app.routers.schemas import (
    ChatRequest,
    FileReadRequest,
    KnowledgeCreateRequest,
    RagRequest,
    SearchRequest,
    SummarizeRequest,
)

# 서비스 Container를 가져옵니다.
from app.services.container import get_container

# 파일 Tool 함수를 가져옵니다.
from app.tools.file_tools import list_doc_files, read_doc_file


# /api 접두어를 사용하는 Router를 생성합니다.
router = APIRouter(prefix="/api", tags=["RAG Assistant"])


# 서버와 설정 상태를 확인하는 API를 정의합니다.
@router.get("/health")
def health() -> dict:
    """현재 앱과 선택된 백엔드 상태를 반환합니다."""

    # 공용 Container를 가져옵니다.
    container = get_container()

    # API 키와 비밀번호는 노출하지 않고 활성화 상태만 반환합니다.
    return {
        "status": "ok",
        "app_name": container.settings.app_name,
        "embedding_backend": container.settings.embedding_backend,
        "vector_backend": container.settings.vector_backend,
        "openai_configured": bool(container.settings.openai_api_key),
        "mysql_enabled": container.settings.mysql_enabled,
    }


# 일반 GPT 질문 API를 정의합니다.
@router.post("/chat")
def chat(request: ChatRequest) -> dict:
    """OpenAI GPT 또는 로컬 대체 응답을 반환합니다."""

    # 공용 Container를 가져옵니다.
    container = get_container()

    # 일반 Assistant Prompt를 조회합니다.
    system_prompt = container.prompt_service.get_prompt("general_assistant")

    # GPT 답변을 생성합니다.
    answer = container.openai_service.answer(request.question, system_prompt)

    # JSON 응답 형태로 반환합니다.
    return {"answer": answer}


# 문서 인덱스 전체 재구축 API를 정의합니다.
@router.post("/rag/rebuild")
def rebuild_rag_index() -> dict:
    """docs 폴더 전체를 벡터 인덱스로 재구축합니다."""

    # 오류를 HTTP 500 응답으로 변환하기 위해 try 블록을 사용합니다.
    try:
        # RAG 인덱스를 재구축하고 결과를 반환합니다.
        return get_container().rag_service.rebuild_index()
    except Exception as exc:
        # 실제 오류 내용을 포함하는 HTTP 예외를 발생시킵니다.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# Vector Search API를 정의합니다.
@router.post("/rag/search")
def search_documents(request: SearchRequest) -> dict:
    """질문과 유사한 문서 청크를 반환합니다. department가 있으면 접근 권한을 적용합니다."""

    # 오류를 HTTP 응답으로 변환하기 위해 try 블록을 사용합니다.
    try:
        # 유사 문서를 검색합니다. (부서 접근 제어 적용)
        results = get_container().rag_service.search(
            request.query, request.top_k, requester_department=request.department
        )

        # 검색 결과 수와 결과 목록을 반환합니다.
        return {"count": len(results), "results": results}
    except Exception as exc:
        # 검색 오류를 HTTP 500으로 반환합니다.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# RAG 질의응답 API를 정의합니다.
@router.post("/rag/ask")
def ask_rag(request: RagRequest) -> dict:
    """검색된 문서를 근거로 GPT 답변을 생성합니다. department가 있으면 접근 권한을 적용합니다."""

    # 오류를 HTTP 응답으로 변환하기 위해 try 블록을 사용합니다.
    try:
        # RAG 답변을 생성하여 반환합니다. (부서 접근 제어 적용)
        return get_container().rag_service.ask(
            request.question, request.top_k, requester_department=request.department
        )
    except Exception as exc:
        # RAG 처리 오류를 HTTP 500으로 반환합니다.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# 문서 1건 전체 요약 API를 정의합니다.
@router.post("/documents/summarize")
def summarize_document(request: SummarizeRequest) -> dict:
    """지정한 문서 전체를 요약합니다. (map-reduce 방식, 긴 문서도 처리 가능)"""

    try:
        return get_container().rag_service.summarize_document(request.filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# 등록된 Prompt 목록 API를 정의합니다.
@router.get("/prompts")
def list_prompts() -> dict:
    """사용 가능한 Prompt 이름을 반환합니다."""

    # Prompt 이름 목록을 반환합니다.
    return {"prompts": get_container().prompt_service.list_prompts()}


# 개별 Prompt 조회 API를 정의합니다.
@router.get("/prompts/{name}")
def get_prompt(name: str) -> dict:
    """이름으로 Prompt 템플릿을 반환합니다."""

    # 존재하지 않는 Prompt 오류를 처리하기 위해 try 블록을 사용합니다.
    try:
        # 요청한 Prompt를 조회하여 반환합니다.
        return {
            "name": name,
            "template": get_container().prompt_service.get_prompt(name),
        }
    except ValueError as exc:
        # 존재하지 않는 Prompt는 HTTP 404로 반환합니다.
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# docs 폴더의 파일 목록 API를 정의합니다.
@router.get("/files")
def list_files() -> dict:
    """MCP 파일 Tool과 동일한 문서 목록 기능을 REST로 제공합니다."""

    # 설정에서 docs 경로를 가져옵니다.
    docs_dir = get_container().settings.docs_dir

    # 파일 목록을 반환합니다.
    return {"files": list_doc_files(docs_dir)}


# docs 폴더 파일 읽기 API를 정의합니다.
@router.post("/files/read")
def read_file(request: FileReadRequest) -> dict:
    """MCP 파일 Tool과 동일한 읽기 기능을 REST로 제공합니다."""

    # 파일 오류를 HTTP 응답으로 변환하기 위해 try 블록을 사용합니다.
    try:
        # 지정한 문서를 읽어 반환합니다.
        content = read_doc_file(get_container().settings.docs_dir, request.filename)

        # 파일명과 내용을 반환합니다.
        return {"filename": request.filename, "content": content}
    except (ValueError, FileNotFoundError) as exc:
        # 잘못된 경로나 없는 파일은 HTTP 400으로 반환합니다.
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# MySQL 예제 테이블 초기화 API를 정의합니다.
@router.post("/mysql/init")
def initialize_mysql() -> dict:
    """MySQL 지식 테이블을 생성합니다."""

    # MySQL 오류를 HTTP 응답으로 변환합니다.
    try:
        # 테이블 초기화 결과를 반환합니다.
        return get_container().mysql_service.initialize()
    except Exception as exc:
        # 연결 또는 SQL 오류를 HTTP 500으로 반환합니다.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# MySQL 지식 목록 API를 정의합니다.
@router.get("/mysql/items")
def list_mysql_items() -> dict:
    """MySQL에 저장된 지식 데이터를 조회합니다."""

    # MySQL 오류를 HTTP 응답으로 변환합니다.
    try:
        # 데이터를 조회합니다.
        items = get_container().mysql_service.list_items()

        # 결과 수와 데이터 목록을 반환합니다.
        return {"count": len(items), "items": items}
    except Exception as exc:
        # 연결 또는 SQL 오류를 HTTP 500으로 반환합니다.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# MySQL 지식 등록 API를 정의합니다.
@router.post("/mysql/items")
def create_mysql_item(request: KnowledgeCreateRequest) -> dict:
    """MySQL에 새 지식 데이터를 저장합니다."""

    # MySQL 오류를 HTTP 응답으로 변환합니다.
    try:
        # 요청 데이터를 저장하고 결과를 반환합니다.
        return get_container().mysql_service.add_item(request.title, request.content)
    except Exception as exc:
        # 연결 또는 SQL 오류를 HTTP 500으로 반환합니다.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# RAG가 실제로 참조하는 문서 목록(경로/부서/버전일자)을 조회하는 API를 정의합니다.
@router.get("/documents")
def list_documents() -> dict:
    """MySQL documents 테이블에 등록된 문서 메타데이터를 조회합니다.

    출처 카드 UI에서 부서/카테고리/버전일자를 보여줄 때 사용합니다.
    document_source=filesystem이면 MySQL 대신 docs 폴더 스캔 결과를 반환합니다.
    """

    container = get_container()

    # mysql 모드가 아니면 파일시스템 스캔 결과를 간단한 형태로 반환합니다.
    if container.settings.document_source.lower() != "mysql":
        files = container.document_service.list_files()
        return {
            "source": "filesystem",
            "count": len(files),
            "documents": [{"filename": f} for f in files],
        }

    # mysql 모드면 DB 오류를 HTTP 응답으로 변환합니다.
    try:
        documents = container.mysql_service.list_documents(active_only=True)
        return {"source": "mysql", "count": len(documents), "documents": documents}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
