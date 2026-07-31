from __future__ import annotations

from typing import Any

from app.agent.state import DataDomain


class MCPClient:
    """애플리케이션이 두 MCP 서버에 접근하는 유일한 어댑터.

    Graph/FastAPI가 FAISS나 MySQL에 직접 접근하지 않도록 도구 이름, 전송 형식, timeout,
    응답 검증을 이 경계에 모은다.
    """
    def __init__(self, document_mcp_url: str, data_mcp_url: str) -> None:
        """각 서버 endpoint를 검증하고 재사용 가능한 비동기 전송 클라이언트를 준비한다."""
        ...

    async def document_search(
        self,
        query: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Document MCP의 search_documents 도구를 호출한다.

        query/top_k를 정확히 전달하고 응답 chunk의 필수 식별자와 출처 메타데이터를
        검증한다. 통신 오류·도구 오류·비정상 payload를 구분해 전파한다.
        """
        ...

    async def finance_query(
        self,
        question: str,
    ) -> list[dict[str, Any]]:
        """Data MCP의 query_finance 도구를 호출하고 표준 근거 목록으로 반환한다.

        SQL을 클라이언트에서 만들거나 수정하지 않으며, 서버가 반환한 행과 실행 메타데이터
        외의 내부 정보는 노출하지 않는다.
        """
        ...

    async def sales_query(
        self,
        question: str,
    ) -> list[dict[str, Any]]:
        """Data MCP의 query_sales 도구를 호출하고 표준 근거 목록으로 반환한다."""
        ...

    async def data_query(
        self,
        domain: DataDomain,
        question: str,
    ) -> list[dict[str, Any]]:
        """명시된 도메인의 Data MCP 도구로만 요청을 전달한다."""
        if domain == "finance":
            return await self.finance_query(question)
        if domain == "sales":
            return await self.sales_query(question)
        raise ValueError(f"지원하지 않는 데이터 도메인입니다: {domain}")


async def document_search(
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """기본 MCPClient를 통한 문서 검색 편의 함수다; 기본 top_k는 정책 상한을 넘지 않는다."""
    ...


async def finance_query(
    question: str,
) -> list[dict[str, Any]]:
    """기본 MCPClient를 통한 재무 데이터 조회 편의 함수다."""
    ...


async def sales_query(
    question: str,
) -> list[dict[str, Any]]:
    """기본 MCPClient를 통한 판매 데이터 조회 편의 함수다."""
    ...
