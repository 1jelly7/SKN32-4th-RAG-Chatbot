"""구매 질문을 제한된 단일 SELECT 초안으로 변환하는 Text2SQL adapter."""

from __future__ import annotations

from app.core.config import get_settings
from mcp_servers.data_tools.purchase.schema import SchemaResource

SYSTEM_PROMPT = (
    "당신은 구매 데이터베이스 전용 SQL 생성기입니다. "
    "제공된 테이블과 컬럼만 사용해 MySQL 단일 SELECT 문을 생성하세요. "
    "쓰기 문장과 DDL을 생성하지 말고 LIMIT을 포함하세요. SQL만 출력하세요."
)

# API 키가 없을 때 쓰는 키워드 -> SQL 템플릿 매핑 (데모/오프라인 모드)
# 더 구체적인(좁은) 질문 패턴을 먼저 검사해야, "공급업체별 지출"처럼 여러 키워드가
# 동시에 들어간 질문에서 의도한 템플릿이 먼저 매칭됩니다.
_FALLBACK_TEMPLATES: list[tuple[tuple[str, ...], str]] = [
    (
        ("지출", "발주액", "구매액", "총액"),
        "SELECT v.vendor_name, COUNT(po.purchase_order_id) AS po_count, "
        "SUM(po.total_amount) AS total_spend FROM purchase_orders po "
        "JOIN vendors v ON po.vendor_id = v.vendor_id GROUP BY v.vendor_name "
        "ORDER BY total_spend DESC LIMIT 20;",
    ),
    (
        ("미지급", "outstanding"),
        "SELECT vendor_id, invoice_number, total_amount, outstanding_amount, status "
        "FROM vendor_invoices WHERE outstanding_amount > 0 "
        "ORDER BY outstanding_amount DESC LIMIT 50;",
    ),
    (
        ("평가", "점수", "rating"),
        "SELECT vendor_id, rating_period, overall_score FROM vendor_ratings "
        "ORDER BY overall_score DESC LIMIT 20;",
    ),
    (
        ("공급업체", "벤더", "vendor"),
        "SELECT vendor_name, vendor_type, country, credit_limit FROM vendors "
        "ORDER BY vendor_name LIMIT 50;",
    ),
]

_DEFAULT_FALLBACK_SQL = "SELECT * FROM purchase_orders ORDER BY po_date DESC LIMIT 20;"


def _generate_sql_fallback(question: str) -> str:
    """API key가 없는 개발 환경에서 제한된 구매 SELECT 템플릿을 선택한다."""
    normalized = question.casefold()
    for keywords, sql in _FALLBACK_TEMPLATES:
        if any(keyword in normalized for keyword in keywords):
            return sql
    return _DEFAULT_FALLBACK_SQL


async def generate_sql(question: str, schema: SchemaResource) -> str:
    """구매 allowlist schema만 사용해 실행 전 재검증할 SELECT 초안을 만든다."""
    settings = get_settings()
    if not settings.openai_api_key:
        return _generate_sql_fallback(question)

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    schema_description = (
        f"테이블: {', '.join(schema['tables'])}\n"
        f"컬럼: {schema['columns']}\n"
        f"용어집: {schema['business_glossary']}"
    )
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"스키마:\n{schema_description}\n\n질문: {question}"},
        ],
        temperature=0,
    )
    sql = response.choices[0].message.content or ""
    return sql.strip().strip("`").removeprefix("sql\n").strip()
