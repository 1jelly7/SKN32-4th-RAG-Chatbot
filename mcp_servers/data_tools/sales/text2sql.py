<<<<<<< HEAD
from __future__ import annotations

from app.core.config import get_settings
from mcp_servers.data_tools.sales.schema import SchemaResource

SYSTEM_PROMPT = (
    "당신은 판매 데이터베이스 전용 SQL 생성기입니다. "
    "제공된 테이블/컬럼만 사용해 MySQL 단일 SELECT 문을 생성하세요. "
    "SELECT 이외의 문장(INSERT/UPDATE/DELETE/DDL)은 절대 생성하지 마세요. "
    "결과 건수를 제한하기 위해 LIMIT을 포함하세요. SQL 코드만 출력하고 설명은 하지 마세요."
)

# 더 구체적인 질문 패턴을 먼저 검사합니다 (finance/text2sql.py와 동일한 원칙).
_FALLBACK_TEMPLATES: list[tuple[tuple[str, ...], str]] = [
    (
        ("vip",),
        "SELECT c.customer_id, c.customer_name, pl.list_name, pl.customer_segment "
        "FROM price_lists pl JOIN customers c ON pl.item_id IS NOT NULL "
        "WHERE pl.customer_segment = 'VIP' LIMIT 50;",
    ),
    (
        ("매출", "revenue", "총액"),
        "SELECT c.customer_name, COUNT(so.sales_order_id) AS order_count, SUM(so.total_amount) AS revenue "
        "FROM sales_orders so JOIN customers c ON so.customer_id = c.customer_id "
        "GROUP BY c.customer_name ORDER BY revenue DESC LIMIT 20;",
    ),
    (
        ("미수금", "outstanding"),
        "SELECT customer_id, invoice_number, total_amount, outstanding_amount, status "
        "FROM invoices WHERE outstanding_amount > 0 ORDER BY outstanding_amount DESC LIMIT 50;",
    ),
    (
        ("재고", "stock"),
        "SELECT item_id, warehouse_id, quantity_on_hand, quantity_available FROM stock_levels ORDER BY quantity_available DESC LIMIT 50;",
    ),
    (
        ("고객", "customer"),
        "SELECT customer_name, customer_type, industry, country FROM customers ORDER BY customer_name LIMIT 50;",
    ),
]

_DEFAULT_FALLBACK_SQL = "SELECT * FROM sales_orders ORDER BY order_date DESC LIMIT 20;"


def _generate_sql_fallback(question: str) -> str:
    for keywords, sql in _FALLBACK_TEMPLATES:
        if any(keyword in question.lower() for keyword in keywords):
            return sql
    return _DEFAULT_FALLBACK_SQL


async def generate_sql(
    question: str,
    schema: SchemaResource,
) -> str:
    """질문과 제공된 스키마로 SELECT SQL 초안을 생성한다. (OPENAI_API_KEY 없으면 템플릿 폴백)"""
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
=======
from mcp_servers.data_tools.sales.schema import SchemaResource


async def generate_sql(question: str, schema: SchemaResource) -> str:
    """판매 도메인에 한정된 단일 SELECT 초안을 만든다."""
    ...
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0
