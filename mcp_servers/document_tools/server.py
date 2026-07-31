from typing import Any

from mcp.server.mcpserver import MCPServer

from mcp_servers.document_tools.search import search_documents


def create_server() -> Any:
    """search_documents 도구를 등록한 Document MCP 서버를 만든다.

    도구 스키마/오류 경계를 정의한다. 내부적으로 문서 DB에서 파일 경로를 조회한 뒤
    파일을 읽지만, 응답에는 내부 파일 경로를 노출하지 않는다.
    """

    server = MCPServer(name="document-mcp", version="0.1.0")

    @server.tool()
    async def search_documents_tool(query: str, top_k: int = 5) -> dict:
        """사내 문서(PDF/TXT/Markdown)에서 질문과 관련된 근거를 검색합니다.

        docs/interface.md의 공통 응답 형식(status/domain/message/data/sources/metadata)에
        맞춰 반환합니다. file_path는 절대 응답에 포함하지 않습니다.
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
            return {
                "status": "error",
                "domain": "document",
                "message": "문서 검색 중 오류가 발생했습니다.",
                "error_code": "INTERNAL_ERROR",
                "data": [],
                "sources": [],
                "metadata": {"detail": str(exc)},
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
                {"document_id": c["document_id"], "title": c["title"]} for c in chunks
            ],
            "metadata": {"result_count": len(chunks)},
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
