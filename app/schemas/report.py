"""리포트 생성 HTTP 요청·응답의 공개 Pydantic 계약.

app/schemas/chat.py와 동일한 원칙 — 내부 조회 로직이나 evidence를 그대로 노출하지
않고, 사용자가 요청/조회할 수 있는 최소 필드만 표현한다.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator


class ReportTemplateInfo(BaseModel):
    """GET /api/reports/templates가 반환하는 템플릿 1개의 요약이다."""

    id: str
    name: str
    description: str


class ReportGenerateRequest(BaseModel):
    """리포트 생성 요청. 데이터 조회 기간은 사용자가 직접 지정한다."""

    template_id: str = Field(min_length=1)
    start_date: date
    end_date: date

    # 추가: 계획에는 없었지만, HTTP 요청 경계에서 받는 값이라 end_date < start_date
    # 같은 뒤집힌 기간을 여기서 걸러내지 않으면 report_service가 만든 질문 문장이
    # ("2026-03-01부터 2026-01-01까지") 그대로 LLM에 들어가 이상한 SQL을 유발할 수
    # 있다.
    @model_validator(mode="after")
    def _check_date_range(self) -> "ReportGenerateRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date는 start_date보다 앞설 수 없습니다.")
        return self
