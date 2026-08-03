"""구매 질문을 시맨틱 레이어(뷰·용어집) 안에서 SELECT SQL로 변환하는 Text2SQL adapter.

LLM에게는 원본 테이블이 아니라 뷰 5개와 컬럼·용어집 정의만 준다("구매액이 뭔지"
같은 판단을 LLM이 하지 못하게). API 키가 없을 때 질문과 무관한 고정 SQL을
돌려주던 이전 fallback은 제거했다 — 조용한 오답보다 시끄러운 실패가 안전하다
(mcp_servers/data_tools/sales/text2sql.py와 동일 원칙).
"""

from __future__ import annotations

from datetime import date

from app.core.config import get_settings
from mcp_servers.data_tools.purchase.schema import SchemaResource

SYSTEM_PROMPT = (
    "당신은 구매 데이터베이스 전용 SQL 생성기입니다. "
    "제공된 뷰(VIEW)와 컬럼만 사용해 MySQL 단일 SELECT 문을 생성하세요. "
    "쓰기 문장과 DDL을 생성하지 말고 LIMIT을 포함하세요. SQL만 출력하세요."
    "당신은 구매 데이터베이스 전용 SQL 생성기입니다. 아래 규칙을 반드시 지키세요.\n"
    "1. 제공된 뷰(view)만 사용하세요. 원본 테이블 이름을 쓰면 권한 오류가 납니다.\n"
    "2. 단일 SELECT 문 하나만 생성하세요. 세미콜론으로 여러 문장을 잇지 마세요.\n"
    "3. 결과 건수를 제한하기 위해 LIMIT을 반드시 포함하세요.\n"
    "4. 아래 [허용된 뷰]에 명시된 컬럼명만 그대로 사용하세요. 존재하지 않는 컬럼을 "
    "만들어내지 마세요.\n"
    "5. 업무 용어(구매액, 미지급액 등)의 정의는 제공된 용어집을 그대로 따르세요. "
    "스스로 다른 컬럼이나 계산식을 만들지 마세요.\n"
    "6. 발주 총액/구매액 집계는 v_purchase_order.total_amount를 쓰세요. "
    "v_purchase_order_line은 품목·상품 단위로 물을 때만 쓰세요(라인에는 헤더 "
    "금액이 없습니다 — fan-out 방지).\n"
    "7. 공급업체의 연락처·주소 같은 PII는 제공된 뷰에 없습니다. 만들어내지 마세요.\n"
    "8. SELECT * 를 쓰지 마세요. 필요한 컬럼만 나열하세요.\n"
    "9. 카테고리 비교(공급업체별, 품목별 등)는 LIMIT 20 이하로 제한하세요.\n"
    "10. 제공된 뷰·용어집으로 답할 수 없거나 범위 밖 질문이면 SQL을 만들지 말고 "
    "정확히 다음 한 줄만 출력하세요: NO_SQL\n"
    "SQL 코드만 출력하고 다른 설명은 하지 마세요."
)

# API 키가 없을 때 쓰는 키워드 -> SQL 템플릿 매핑 (데모/오프라인 모드)
_FALLBACK_TEMPLATES: list[tuple[tuple[str, ...], str]] = [
    (
        ("지출", "발주액", "구매액", "총액"),
        "SELECT vendor_id, COUNT(po_id) as po_count, SUM(total_amount) as total_spend "
        "FROM v_purchase_order GROUP BY vendor_id ORDER BY total_spend DESC LIMIT 20;",
    ),
    (
        ("미지급", "outstanding"),
        "SELECT vendor_id, invoice_number, total_amount, outstanding_amount, status "
        "FROM v_vendor_invoice WHERE outstanding_amount > 0 "
        "ORDER BY outstanding_amount DESC LIMIT 50;",
    ),
    (
        ("상태", "Closed", "Sent"),
        "SELECT status, COUNT(po_id) as count, SUM(total_amount) as total "
        "FROM v_purchase_order GROUP BY status ORDER BY total DESC LIMIT 20;",
    ),
    (
        ("공급업체", "벤더", "vendor"),
        "SELECT vendor_id, vendor_name, country, payment_terms FROM v_vendor "
        "ORDER BY vendor_name LIMIT 50;",
    ),
    (
        ("품목", "상품", "구매"),
        "SELECT description, SUM(quantity) as total_qty, SUM(line_total) as total_amount "
        "FROM v_purchase_order_line GROUP BY description "
        "ORDER BY total_qty DESC LIMIT 20;",
    ),
]

_DEFAULT_FALLBACK_SQL = "SELECT * FROM v_purchase_order ORDER BY po_date DESC LIMIT 20;"
<<<<<<< Updated upstream
def _format_schema(schema: SchemaResource) -> str:
    """스키마 Resource를 LLM 프롬프트에 넣을 텍스트로 직렬화한다."""
    views = schema.get("views", [])
    view_columns = schema.get("view_columns", {})
    glossary = schema.get("business_glossary", {})
    out_of_scope = schema.get("out_of_scope", [])
    data_range = schema.get("data_range", {})

    views_desc = "\n".join(
        f"- {name}({', '.join(view_columns.get(name, []))})" for name in views
    )

_DEFAULT_FALLBACK_SQL = "SELECT * FROM v_purchase_order ORDER BY po_date DESC LIMIT 20;"
    glossary_lines = []
    for term, definition in glossary.items():
        if isinstance(definition, dict):
            continue  # 상태값 등 중첩 딕셔너리는 SQL 생성에 직접 필요하지 않으므로 건너뜀
        glossary_lines.append(f"- {term}: {definition}")
    glossary_desc = "\n".join(glossary_lines)

    return (
        f"[허용된 뷰]\n{views_desc}\n\n"
        f"[업무 용어 정의]\n{glossary_desc}\n\n"
        f"[답할 수 없는 질문 예시] {', '.join(out_of_scope)}\n\n"
        f"[데이터 보유 기간] {data_range}\n"
    )
=======
>>>>>>> Stashed changes


async def _call_llm(user_content: str) -> str:
    """OpenAI를 호출해 SQL 텍스트를 받는다.

    OPENAI_API_KEY가 없으면 예외를 그대로 낸다. mcp_servers/data_tools/server.py가
    이 예외를 QUERY_ERROR로 변환하므로, 조용히 질문과 무관한 SQL을 실행하던 이전
    fallback 방식보다 안전하다.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않아 SQL을 생성할 수 없습니다.")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # 스키마 설명 구성 (뷰 기반)
    views = schema.get("views", schema.get("tables", []))
    columns = schema.get("columns", {})
    glossary = schema.get("business_glossary", {})

    schema_description = (
        f"허용된 뷰 (5개): {', '.join(views)}\n\n"
        f"각 뷰의 컬럼:\n"
    )

    for view, cols in columns.items():
        schema_description += f"  {view}: {', '.join(cols)}\n"

    schema_description += f"\n업무 용어:\n"
    for i, (term, definition) in enumerate(glossary.items()):
        if i >= 10:  # 처음 10개만
            break
        schema_description += f"  {term}: {definition}\n"

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
    )

<<<<<<< Updated upstream
    text = response.choices[0].message.content or ""
    return text.strip().strip("`").removeprefix("sql\n").strip()


def _extract_sql(raw: str) -> str:
    """LLM 응답에서 'NO_SQL'이면 빈 문자열로, 아니면 원문 그대로 반환한다."""
    if raw.strip().upper() == "NO_SQL":
        return ""
    return raw


async def generate_sql(question: str, schema: SchemaResource) -> str:
    """질문과 오늘 날짜를 스키마 정보와 함께 LLM에 전달해 SELECT SQL을 만든다.

    답할 수 없다고 판단되면 빈 문자열을 반환한다(호출부가 범위 밖으로 처리).
    """
    today = date.today().isoformat()
    user_content = f"{_format_schema(schema)}\n\n[오늘 날짜] {today}\n\n[질문] {question}"
    return _extract_sql(await _call_llm(user_content))


async def generate_sql_with_error(
    question: str,
    schema: SchemaResource,
    failed_sql: str,
    error: str,
) -> str:
    """EXPLAIN 또는 실행이 실패했을 때, 실패한 SQL과 오류 메시지를 보여주고 다시 작성시킨다.

    호출부(query.py)가 이 함수를 최대 1회만 부른다 — 무한 재시도로 비용이 커지는
    것을 막기 위해서다.
    """
    today = date.today().isoformat()
    user_content = (
        f"{_format_schema(schema)}\n\n[오늘 날짜] {today}\n\n[질문] {question}\n\n"
        f"[이전 시도 SQL]\n{failed_sql}\n\n[오류 메시지]\n{error}\n\n"
        "위 오류를 고쳐서 SQL을 다시 작성하세요."
    )
    return _extract_sql(await _call_llm(user_content))


=======
>>>>>>> Stashed changes
    sql = response.choices[0].message.content or ""
    return sql.strip().strip("`").removeprefix("sql\n").strip()