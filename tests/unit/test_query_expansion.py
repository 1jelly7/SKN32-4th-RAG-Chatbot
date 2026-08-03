"""사내 문서 검색어 확장과 결과 병합을 검증한다."""

from __future__ import annotations

import pytest

from app.agent.nodes import document_retrieval
from app.agent.query_expansion import MAX_DOCUMENT_QUERIES, expand_document_queries
from app.mcp.client import FakeMCPPort, MCPClient


@pytest.mark.parametrize(
    ("question", "expected_term"),
    [
        ("겸직 가능 여부", "이중취업"),
        ("회사 카드 정산 방법", "법인카드"),
        ("부당한 업무 지시 신고", "고충처리"),
        ("급여 외 혜택", "복리후생"),
        ("취업 규정", "복무규정"),
        ("수입금 징수 절차", "금전 수납"),
        ("특별 안전 보건 교육 대상", "산업안전 교육"),
    ],
)
def test_expand_document_queries_adds_expected_synonym(
    question: str,
    expected_term: str,
) -> None:
    queries = expand_document_queries(question)

    assert queries[0] == question
    assert expected_term in " ".join(queries[1:])
    assert len(queries) <= MAX_DOCUMENT_QUERIES


@pytest.mark.asyncio
async def test_document_retrieval_expands_only_when_direct_score_is_low() -> None:
    port = FakeMCPPort(
        {
            "search_documents": {
                "status": "success",
                "domain": "document",
                "message": None,
                "data": [{"content": "카드 관련 문서", "score": 0.1}],
                "sources": [{"document_id": "policy-card", "title": "법인카드 지침", "page": 2}],
                "metadata": {},
            }
        }
    )

    result = await document_retrieval(
        {"question": "회사 카드 사용 방법", "route": "DOCUMENT"},
        MCPClient(port),
    )

    assert [call.tool_name for call in port.calls] == ["search_documents", "search_documents"]
    assert len(result["document_evidence"]) == 1


@pytest.mark.asyncio
async def test_document_retrieval_skips_expansion_for_strong_direct_match() -> None:
    port = FakeMCPPort(
        {
            "search_documents": {
                "status": "success",
                "domain": "document",
                "message": None,
                "data": [{"content": "카드 발급과 정산 절차", "score": 0.9}],
                "sources": [{"document_id": "policy-card", "title": "법인카드 지침", "page": 2}],
                "metadata": {},
            }
        }
    )

    await document_retrieval(
        {"question": "회사 카드 사용 방법", "route": "DOCUMENT"},
        MCPClient(port),
    )

    assert [call.tool_name for call in port.calls] == ["search_documents"]


@pytest.mark.asyncio
async def test_document_retrieval_uses_semantic_document_query() -> None:
    port = FakeMCPPort(
        {
            "search_documents": {
                "status": "success",
                "domain": "document",
                "message": None,
                "data": [{"content": "겸직 승인 절차", "score": 0.9}],
                "sources": [{"document_id": "policy-job", "title": "취업규칙", "page": 4}],
                "metadata": {},
            }
        }
    )

    await document_retrieval(
        {
            "question": "다른 직장에서 일을 병행해도 되나요?",
            "document_search_query": "겸직 겸업 규정",
            "route": "DOCUMENT",
        },
        MCPClient(port),
    )

    assert port.calls[0].payload["query"] == "겸직 겸업 규정"
