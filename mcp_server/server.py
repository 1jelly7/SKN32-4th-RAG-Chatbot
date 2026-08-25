"""
Tool, Resource, Prompt를 등록해서 제공하는 독립 MCP 서버
"""

# MCP 객체 생성용
from mcp.server.fastmcp import FastMCP
from pip._internal.utils import retry

# Resource 등록을 위해 리소스 가져옴
from mcp_server.resources import document_catalog, runtime_config

# Tool 등록을 위해 툴 가져옴
from mcp_server.tools import (
    add_numbers,
    ask_rag,
    list_files,
    list_mysql_knowledge,
    read_file,
    rebuild_index,
    search_documents,
)

# 서버 객체 생성 =====================================
mcp = FastMCP("MCP RAG Assistant")

# Tool 등록================================================
# 별도로 작성해서 임포트한 함수를 Tool로 등록하는 방법


# 계산 Tool을 MCP에 등록
@mcp.tool()
def add(a: float, b: float) -> float:
    """두 숫자를 더합니다."""

    # 준비된 함수에 처리를 위임(weaving)함
    return add_numbers(a, b)


@mcp.tool()
def add(a: float, b: float) -> float:
    """두 숫자를 더합니다."""
    # 준비된 함수에 처리를 위임(weaving)함
    return add_numbers(a, b)


@mcp.tool()
def list_docs() -> list[str]:
    """MCP Client가 사용할 수 있는 문서 파일 목록을 반환합니다."""
    # 준비된 함수에 처리를 위임(weaving)함
    return list_files()


@mcp.tool()
def read_doc(filename: str) -> str:
    """지정한 문서 파일(filename)의 내용을 읽어서 반환합니다."""
    # 준비된 함수에 처리를 위임(weaving)함
    return read_file(filename)


@mcp.tool()
def search_docs(query: str, top_k: int = 4) -> list[dict]:
    """FAISS 또는 Qdrant 벡터 데이터베이스에서 쿼리와 유사한 문서 내용을 검색합니다."""
    # 준비된 함수에 처리를 위임(weaving)함
    return search_documents(query, top_k)


@mcp.tool()
def rebuild_vector_index() -> dict:
    """docs 폴더의 전체 문서들을 벡터 저장소에 다시 분석 및 적재(인덱스 재구축)합니다."""
    # 준비된 함수에 처리를 위임(weaving)함
    return rebuild_index()


@mcp.tool()
def ask_rag_question(question: str, top_k: int = 4) -> dict:
    """질문(question)에 대해 벡터 검색 결과를 근거로 답변과 출처를 함께 생성하여 반환합니다."""
    # 준비된 함수에 처리를 위임(weaving)함
    return ask_rag(question, top_k)


@mcp.tool()
def get_mysql_knowledge() -> list[dict]:
    """MySQL 데이터베이스의 knowledge_items 테이블에 저장된 지식 목록을 조회하여 반환합니다."""
    # 준비된 함수에 처리를 위임(weaving)함
    return list_mysql_knowledge()


# 별도로 작성해서 임포트한 리소스 등록 ====================================


# 현재 실행 설정 Resource 등록
@mcp.resource("config://runtime")
def config_resource() -> str:
    """민감 정보 제외한 실행 설정 정보 제공"""
    # Resource 구현 함수를 호출함
    return runtime_config()


# 문서 카탈로그 Resource 등록
@mcp.tool("docs://catalog")
def docs_catalog() -> str:
    """docs 폴더의 파일 목록을 제공"""
    # Resource 구현 함수를 호출
    return document_catalog()


@mcp.prompt()
def ground_rag_prompt(question: str) -> str:
    return (
        "먼저 vector_search 또는 rag_question_answer Tppl을 사용하세요\n"
        "검색 결과에 포함된 문서만 근거로 답하세요\n"
        "확인할 수 없는 내용은 추측하지 마세요.\n\n"
        f"사용자 질문:{question}"
    )


# 서버 파일을 직접 실행했을 때 stdio 전송 방식으로 MCP 서버를 시작합니다.
if __name__ == "__main__":
    # MCP Client와 표준 입력·출력
    mcp.run(transport="stdio")
