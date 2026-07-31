<<<<<<< HEAD
"""app/agent(router, evidence_eval, graph)를 검증합니다.

MySQL(erp_system/purchase/sales)이 로컬에 준비되어 있으면 전체 그래프까지
실제로 실행해서 검증하고, 없으면 자동으로 건너뜁니다.
"""

from __future__ import annotations

import pytest

from app.agent.nodes import route_data_domain, route_question


# ------------------------------------------------------------------
# route_question / route_data_domain (순수 함수, 외부 의존성 없음)
# ------------------------------------------------------------------
@pytest.mark.parametrize(
    "question,expected",
    [
        ("휴가 규정이 어떻게 되나요", "DOCUMENT"),
        ("법인카드 지침 알려줘", "DOCUMENT"),
        ("고객별 매출 순위 알려줘", "DATABASE"),
        ("공급업체별 지출 총액이 얼마야", "DATABASE"),
        ("법인카드 지침이랑 매출 현황 같이 알려줘", "BOTH"),
        ("오늘 날씨 어때", "GENERAL"),
    ],
)
def test_route_question_classifies_correctly(question, expected):
    assert route_question(question) == expected


def test_route_data_domain_detects_sales():
    assert route_data_domain("고객별 매출 순위") == "sales"


def test_route_data_domain_detects_finance():
    assert route_data_domain("공급업체별 지출 총액") == "finance"


def test_route_data_domain_defaults_to_both_when_ambiguous():
    assert route_data_domain("이번 분기 실적 알려줘") == "both"


# ------------------------------------------------------------------
# evidence_eval (순수 함수, 외부 의존성 없음)
# ------------------------------------------------------------------
@pytest.mark.asyncio
async def test_evidence_eval_insufficient_when_no_evidence():
    from app.agent.evidence_eval import evidence_eval

    state = {"route": "DOCUMENT", "document_evidence": [], "database_evidence": []}
    result = await evidence_eval(state)
    assert result["evidence_status"] == "INSUFFICIENT"


@pytest.mark.asyncio
async def test_evidence_eval_supported_when_evidence_present():
    from app.agent.evidence_eval import evidence_eval

    state = {
        "route": "DOCUMENT",
        "document_evidence": [{"type": "document", "content": "내용"}],
        "database_evidence": [],
    }
    result = await evidence_eval(state)
    assert result["evidence_status"] == "SUPPORTED"


@pytest.mark.asyncio
async def test_evidence_eval_general_route_skips_check():
    from app.agent.evidence_eval import evidence_eval

    state = {"route": "GENERAL"}
    result = await evidence_eval(state)
    assert result["evidence_status"] == "SUPPORTED"
    assert result["evidence"] == []


# ------------------------------------------------------------------
# 전체 그래프 (실제 MySQL 필요 - 없으면 skip)
# ------------------------------------------------------------------
def _mysql_available() -> bool:
    try:
        from app.core.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()
        import pymysql

        conn = pymysql.connect(
            host=settings.mysql_read_host,
            user=settings.mysql_read_user,
            password=settings.mysql_read_password,
            database=settings.document_db_database,
        )
        conn.close()
        return True
    except Exception:
        return False


MYSQL_READY = _mysql_available()
skip_without_mysql = pytest.mark.skipif(not MYSQL_READY, reason="로컬에 MySQL(erp_system/purchase/sales)이 준비되어 있지 않습니다")


@skip_without_mysql
@pytest.mark.asyncio
async def test_graph_document_route_end_to_end():
    from app.agent.graph import get_graph

    graph = get_graph()
    result = await graph.ainvoke({"question": "법인카드 사용 지침이 뭐야"})

    assert result["route"] == "DOCUMENT"
    assert result["answer"]
    assert len(result["sources"]) > 0


@skip_without_mysql
@pytest.mark.asyncio
async def test_graph_database_route_end_to_end():
    from app.agent.graph import get_graph

    graph = get_graph()
    result = await graph.ainvoke({"question": "고객별 매출 순위 알려줘"})

    assert result["route"] == "DATABASE"
    assert result["data_domain"] == "sales"
    assert result["answer"]


@skip_without_mysql
@pytest.mark.asyncio
async def test_graph_both_route_collects_both_evidence():
    from app.agent.graph import get_graph

    graph = get_graph()
    result = await graph.ainvoke({"question": "법인카드 지침이랑 매출 현황 같이 알려줘"})

    assert result["route"] == "BOTH"
    assert len(result["document_evidence"]) > 0
    assert len(result["database_evidence"]) > 0


@skip_without_mysql
@pytest.mark.asyncio
async def test_graph_general_route_skips_retrieval():
    from app.agent.graph import get_graph

    graph = get_graph()
    result = await graph.ainvoke({"question": "오늘 기분이 어때"})

    assert result["route"] == "GENERAL"
    assert result.get("document_evidence", []) == []
    assert result.get("database_evidence", []) == []
=======
from app.agent.nodes import route_question
def test_router_document(): assert route_question('휴가 정책 문서를 알려줘') == 'DOCUMENT'
def test_router_data(): assert route_question('지난달 매출 알려줘') == 'DATABASE'
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0
