from __future__ import annotations

from app.core.config import get_settings
from mcp_servers.data_tools.finance.schema import SchemaResource

SYSTEM_PROMPT = (
    "당신은 재무/구매 데이터베이스 전용 SQL 생성기입니다. "
    "제공된 테이블/컬럼만 사용해 MySQL 단일 SELECT 문을 생성하세요. "
    "SELECT 이외의 문장(INSERT/UPDATE/DELETE/DDL)은 절대 생성하지 마세요. "
    "결과 건수를 제한하기 위해 LIMIT을 포함하세요. SQL 코드만 출력하고 설명은 하지 마세요."
)

# API 키가 없을 때 쓰는 키워드 -> SQL 템플릿 매핑 (데모/오프라인 모드)
# 더 구체적인(좁은) 질문 패턴을 먼저 검사해야, "공급업체별 지출"처럼 여러 키워드가
# 동시에 들어간 질문에서 의도한 템플릿이 먼저 매칭됩니다.
_FALLBACK_TEMPLATES: list[tuple[tuple[str, ...], str]] = [
    (
        ("지출", "발주액", "구매액", "총액", "총 지출"),
        "SELECT v.vendor_name, COUNT(po.purchase_order_id) AS po_count, SUM(po.total_amount) AS total_spend "
        "FROM purchase_orders po JOIN vendors v ON po.vendor_id = v.vendor_id "
        "GROUP BY v.vendor_name ORDER BY total_spend DESC LIMIT 20;",
    ),
    (
        ("미지급", "미수금", "outstanding"),
        "SELECT vendor_id, invoice_number, total_amount, outstanding_amount, status "
        "FROM vendor_invoices WHERE outstanding_amount > 0 ORDER BY outstanding_amount DESC LIMIT 50;",
    ),
    (
        ("평가", "점수", "rating"),
        "SELECT vendor_id, rating_period, overall_score FROM vendor_ratings ORDER BY overall_score DESC LIMIT 20;",
    ),
    (
        ("공급업체", "벤더", "vendor"),
        "SELECT vendor_name, vendor_type, country, credit_limit FROM vendors ORDER BY vendor_name LIMIT 50;",
    ),
]

_DEFAULT_FALLBACK_SQL = "SELECT * FROM purchase_orders ORDER BY po_date DESC LIMIT 20;"


def _generate_sql_fallback(question: str) -> str:
    """API 키가 없을 때 쓰는 간단한 키워드 매칭 기반 SQL 생성(데모용)."""
    for keywords, sql in _FALLBACK_TEMPLATES:
        if any(keyword in question for keyword in keywords):
            return sql
    return _DEFAULT_FALLBACK_SQL


async def generate_sql(
    question: str,
    schema: SchemaResource,
) -> str:
    """질문과 제공된 스키마로 SELECT SQL 초안을 생성한다.

    프롬프트는 제공된 테이블·컬럼만 사용하고 단일 SELECT와 결과 건수 제한을 요구한다.
    OPENAI_API_KEY가 없으면 키워드 매칭 기반 템플릿으로 대체한다(오프라인/데모 모드).
    """
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
    # 코드블록으로 감싸서 응답하는 경우가 많아 마크다운 펜스를 제거합니다.
    return sql.strip().strip("`").removeprefix("sql\n").strip()
