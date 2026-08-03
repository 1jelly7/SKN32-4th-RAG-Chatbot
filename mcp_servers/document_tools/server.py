"""문서 DB 경로 조회와 RAG 검색을 search_documents Tool로 공개한다."""

from typing import Any

from mcp.server.mcpserver import MCPServer

from app.logging import get_logger
from mcp_servers.document_tools.rag import get_last_index_version
from mcp_servers.document_tools.search import search_documents

logger = get_logger(__name__)


def create_server() -> Any:
    """search_documents 도구를 등록한 Document MCP 서버를 만든다.

    도구 스키마/오류 경계를 정의한다. 내부적으로 문서 DB에서 파일 경로를 조회한 뒤
    파일을 읽지만, 응답에는 내부 파일 경로를 노출하지 않는다.
    """

    server = MCPServer(name="document-mcp", version="0.1.0")

    @server.tool()
    async def search_documents_tool(query: str, top_k: int = 5) -> dict:
        """사내 문서(PDF/TXT/Markdown)에서 질문과 관련된 근거를 검색합니다.

        규정·정책·가이드처럼 사내 문서 근거가 필요한 질문에만 사용한다. 반환 envelope의
        data는 근거 내용/점수, sources는 공개 문서 식별자를 뜻한다. 업무 수치 조회나
        임의 파일 접근에는 사용하지 않고 file_path는 절대 응답에 포함하지 않는다.
        """
        if not query or not query.strip():
            return {
                "status": "error",
                "domain": "document",
                "message": "질문이 비어 있습니다.",
                "error_code": "INVALID_INPUT",
                "data": [],
                "sources": [],
                "metadata": {},
            }

        try:
            chunks = await search_documents(query, top_k=top_k)
        except Exception as exc:  # noqa: BLE001 - 사용자에게는 일반화된 오류만 노출합니다.
            # 원본 예외는 서버 내부 로그로만 남기고, 외부 응답에는 절대 포함하지 않습니다.
            # (내부 file_path, DB 드라이버 메시지 등 민감정보가 노출될 수 있기 때문)
            logger.error("document_search 내부 오류: %s", exc, exc_info=True)
            return {
                "status": "error",
                "domain": "document",
                "message": "문서 검색 중 오류가 발생했습니다.",
                "error_code": "INTERNAL_ERROR",
                "data": [],
                "sources": [],
                "metadata": {},
            }

        if not chunks:
            return {
                "status": "error",
                "domain": "document",
                "message": "관련 문서를 찾지 못했습니다.",
                "error_code": "NO_RESULT",
                "data": [],
                "sources": [],
                "metadata": {"result_count": 0},
            }

        return {
            "status": "success",
            "domain": "document",
            "message": None,
            "data": [{"content": c["content"], "score": c["score"]} for c in chunks],
            "sources": [
                {"document_id": c["document_id"], "title": c["title"], "page": c.get("page")} for c in chunks
            ],
            "metadata": {"result_count": len(chunks), "index_version": get_last_index_version()},
        }

    return server


def main() -> None:
    """검증된 환경 설정으로 Document MCP 서버를 시작하는 CLI 진입점이다."""

    # 환경설정이 잘못되어 있으면(DB 접속 정보 등) 서버 기동 전에 바로 알 수 있도록
    # 여기서 한 번 로드해봅니다.
    from app.core.config import get_settings

    get_settings()

    server = create_server()
    server.run()


if __name__ == "__main__":
    main()
