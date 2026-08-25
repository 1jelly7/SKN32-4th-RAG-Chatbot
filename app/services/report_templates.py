"""리포트 템플릿의 정적 정의(스키마·지표를 하드코딩하는 mcp_servers/data_tools/*/schema.py와
동일한 패턴) — 실제 조회(app/services/report_service.py, 5단계)와 문서 조립
(app/services/docx_builder.py, 4단계)에서 재사용할 섹션 스펙만 담는다.

지금은 템플릿 1개("sales_monthly")만 정의한다. 섹션의 question_template은
{start_date}/{end_date} placeholder를 포함하며, 실제 기간 문자열을 채우는 일은
이 파일의 책임이 아니라 report_service.py(5단계)가 한다.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from app.schemas.report import ReportTemplateInfo


class ReportSectionSpec(TypedDict):
    """리포트 한 섹션의 제목·조회 도메인·질문 템플릿."""

    title: str
    domain: Literal["purchase", "sales"]
    question_template: str


class ReportTemplateSpec(TypedDict):
    """리포트 템플릿 1개(식별자·표시용 이름/설명·섹션 목록)."""

    id: str
    name: str
    description: str
    sections: list[ReportSectionSpec]


_TEMPLATES: dict[str, ReportTemplateSpec] = {
    "sales_monthly": {
        "id": "sales_monthly",
        "name": "월간 매출 리포트",
        "description": "매출 추이·고객별 순위·미수금 현황을 한 문서로 묶은 판매 리포트.",
        "sections": [
            {
                "title": "매출 추이",
                "domain": "sales",
                "question_template": "{start_date}부터 {end_date}까지 월별 매출 추이를 알려줘",
            },
            {
                "title": "고객별 순위",
                "domain": "sales",
                "question_template": "{start_date}부터 {end_date}까지 매출 상위 고객 순위를 알려줘",
            },
            {
                "title": "미수금 현황",
                "domain": "sales",
                "question_template": "{start_date}부터 {end_date}까지 미수금 현황을 알려줘",
            },
        ],
    },
}


def list_templates() -> list[ReportTemplateInfo]:
    """등록된 템플릿 전체를 API 응답용 요약으로 변환한다."""
    return [
        ReportTemplateInfo(id=spec["id"], name=spec["name"], description=spec["description"])
        for spec in _TEMPLATES.values()
    ]


def get_template(template_id: str) -> ReportTemplateSpec:
    """template_id로 템플릿 스펙을 찾는다.

    없으면 KeyError를 낸다 — app/api/reports.py(6단계)가 이를 404로 변환한다.
    """
    try:
        return _TEMPLATES[template_id]
    except KeyError as exc:
        raise KeyError(f"등록되지 않은 리포트 템플릿입니다: {template_id}") from exc
