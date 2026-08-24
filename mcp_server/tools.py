"""
MCP Server에서 제공할 Tool 함수를 정의합니다.
"""

# 서비스 Container를 가져옵니다.
from app.services.container import get_container

# 파일 Tool 구현을 가져옵니다.
from app.tools.file_tools import list_doc_files, read_doc_file


# 두 숫자를 더합니다.
def add_numbers(a: float, b: float) -> float:
    """두 숫자의 합을 반환합니다."""

    # 두 숫자를 더한 결과를 반환합니다.
    return a + b


# docs 폴더의 파일 목록을 반환합니다.
def list_files() -> list[str]:
    """MCP Client가 사용할 수 있는 문서 파일 목록을 반환합니다."""

    # Container 설정에서 docs 경로를 가져옵니다.
    docs_dir = get_container().settings.docs_dir

    # 공통 파일 Tool로 목록을 반환합니다.
    return list_doc_files(docs_dir)


# docs 폴더의 파일을 읽습니다.
def read_file(filename: str) -> str:
    """지정한 문서 파일 내용을 반환합니다."""

    # Container 설정에서 docs 경로를 가져옵니다.
    docs_dir = get_container().settings.docs_dir

    # 안전한 공통 파일 Tool을 호출합니다.
    return read_doc_file(docs_dir, filename)


# 벡터 문서 검색을 수행합니다.
def search_documents(query: str, top_k: int = 4) -> list[dict]:
    """FAISS 또는 Qdrant에서 유사 문서를 검색합니다."""

    # RAG 서비스의 검색 기능을 호출하여 결과를 반환합니다.
    return get_container().rag_service.search(query, top_k)


# 문서 인덱스를 재구축합니다.
def rebuild_index() -> dict:
    """docs 폴더 전체를 벡터 저장소에 다시 적재합니다."""

    # RAG 서비스의 인덱스 재구축 기능을 호출합니다.
    return get_container().rag_service.rebuild_index()


# RAG 답변을 생성합니다.
def ask_rag(question: str, top_k: int = 4) -> dict:
    """검색 문서를 근거로 답변과 출처를 반환합니다."""

    # RAG 서비스의 질의응답 기능을 호출합니다.
    return get_container().rag_service.ask(question, top_k)


# MySQL 지식 목록을 조회합니다.
def list_mysql_knowledge() -> list[dict]:
    """MySQL knowledge_items 테이블 데이터를 반환합니다."""

    # MySQL 서비스의 조회 기능을 호출합니다.
    return get_container().mysql_service.list_items()
