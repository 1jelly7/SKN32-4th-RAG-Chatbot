"""리포트 템플릿의 섹션들을 병렬 조회해 .docx로 조립하는 오케스트레이션.

MCP 호출(app/mcp/client.py)과 표 변환(app/agent/nodes.py::build_tables)만 담당하고,
실제 SQL 생성·실행은 각 도메인 MCP tool 안에서만 일어난다. 문서 조립 자체는
app/services/docx_builder.py(4단계, 데이터 조회 없는 순수 함수)에 위임한다.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date
from typing import Any

from app.agent.nodes import build_tables
from app.mcp.client import MCPClient, MCPNoResultError
from app.services.docx_builder import SectionResult, build_report_docx
from app.services.report_templates import ReportSectionSpec, get_template

# 섹션 제목·행 수·조회 기간만으로 서술 문단을 만드는 함수의 시그니처. 지금은
# 고정 문구(_default_narrative)만 쓰지만, 나중에 LLM 요약으로 바꿔 끼울 수 있도록
# 주입 지점을 분리해뒀다(app/agent/nodes.py의 llm/web_search 주입 패턴과 동일).
NarrativeFn = Callable[[str, int, date, date], str]


def _default_narrative(title: str, row_count: int, start_date: date, end_date: date) -> str:
    """행 수·조회 기간만 담은 임시 서술 문구. LLM 요약을 붙이기 전까지 사용한다."""
    period = f"{start_date.isoformat()} ~ {end_date.isoformat()}"
    if row_count == 0:
        return f"{period} 기간에 조회된 데이터가 없습니다."
    return f"{period} 기간 조회 결과 {row_count}건입니다."


def _extract_chart_hint(evidence: list[dict[str, Any]]) -> str | None:
    """evidence의 metadata.chart_hint를 읽는다.

    build_tables()가 반환하는 표 dict에는 chart_hint/chart_type이 없다(app/schemas/chat.py의
    TableData.chart_type도 현재 항상 None으로만 내려가는 미배선 필드다 — 이번 작업과
    무관한 기존 간극이라 여기서 고치지 않는다). 대신 mcp_servers/data_tools/*/query.py의
    _chart_hint()가 이미 계산해 evidence의 metadata에 실어 보내는 값을 여기서 직접 읽는다.
    """
    if not evidence:
        return None
    metadata = evidence[0].get("metadata")
    if not isinstance(metadata, dict):
        return None
    hint = metadata.get("chart_hint")
    return hint if hint in ("bar", "line") else None


async def _fetch_section(
    spec: ReportSectionSpec,
    start_date: date,
    end_date: date,
    mcp_client: MCPClient,
    user_context: dict[str, object] | None,
    narrative_fn: NarrativeFn,
) -> SectionResult:
    """섹션 질문 하나를 조회해 SectionResult로 만든다.

    MCPNoResultError(해당 기간에 데이터 없음)는 빈 섹션으로 처리한다 — 리포트
    기간에 따라 흔히 있는 정상 상황이라, 이것 때문에 문서 생성 전체를 실패시키지
    않는다. 그 외 MCPClientError(권한 없음, 조회 오류, timeout 등)는 삼키지 않고
    그대로 올려 generate_report() 전체가 실패하게 한다 — "데이터가 없다"와 "조회
    자체가 안 됐다"를 같은 빈 섹션으로 위장하면 안 되기 때문이다.
    """
    question = spec["question_template"].format(
        start_date=start_date.isoformat(), end_date=end_date.isoformat()
    )
    try:
        # 주의: MCPClient.data_query()는 user_context를 받지 않아(app/mcp/client.py),
        # 그걸 쓰면 실 인증 경로(require_database_access)에서 항상 FORBIDDEN이 난다.
        # app/agent/nodes.py::database_retrieval()과 동일하게 도메인별 메서드를
        # user_context와 함께 직접 호출한다. ReportSectionSpec.domain은 "both"가
        # 될 수 없으므로(app/services/report_templates.py) 분기 2개면 충분하다.
        if spec["domain"] == "purchase":
            evidence = await mcp_client.purchase_query(
                question, user_context=user_context
            )
        else:
            evidence = await mcp_client.sales_query(
                question, user_context=user_context
            )
    except MCPNoResultError:
        evidence = []

    tables = build_tables(evidence)
    # 섹션 질문은 의도적으로 단일 결과 형태만 요구하도록 만들어서(1단계), 정상
    # 흐름에서는 표가 1개만 나온다. 혹시 2개 이상 나오면(예: 질문이 실수로 복합
    # 질문처럼 해석된 경우) 첫 번째 표만 쓴다 — 섹션 1개당 표 1개인 문서 구조를
    # 유지하기 위해서다.
    table = tables[0] if tables else None

    if table is None:
        return SectionResult(
            title=spec["title"],
            narrative=narrative_fn(spec["title"], 0, start_date, end_date),
        )

    return SectionResult(
        title=spec["title"],
        narrative=narrative_fn(spec["title"], len(table["rows"]), start_date, end_date),
        columns=table["columns"],
        rows=table["rows"],
        chartable=table["chartable"],
        chart_type=_extract_chart_hint(evidence),
        label_column=table["label_column"],
        value_column=table["value_column"],
    )


async def generate_report(
    template_id: str,
    start_date: date,
    end_date: date,
    mcp_client: MCPClient,
    user_context: dict[str, object] | None = None,
    narrative_fn: NarrativeFn | None = None,
) -> bytes:
    """템플릿 섹션들을 병렬 조회해 표/차트로 바꾸고 .docx bytes로 조립한다.

    template_id가 등록되지 않았으면 report_templates.get_template()이 던지는
    KeyError를 그대로 올린다 — app/api/reports.py(6단계)가 404로 변환한다.
    """
    template = get_template(template_id)
    fill_narrative = narrative_fn or _default_narrative

    sections = await asyncio.gather(
        *(
            _fetch_section(
                spec, start_date, end_date, mcp_client, user_context, fill_narrative
            )
            for spec in template["sections"]
        )
    )

    return build_report_docx(template["name"], start_date, end_date, list(sections))
