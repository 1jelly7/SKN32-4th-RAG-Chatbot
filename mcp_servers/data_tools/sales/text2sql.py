"""판매 질문을 시맨틱 레이어(뷰·지표) 안에서 SELECT SQL로 변환하는 Text2SQL adapter.

LLM에게는 원본 테이블이 아니라 뷰 5개와 지표 정의만 준다("매출이 뭔지" 같은 판단을
LLM이 하지 못하게). API 키가 없을 때 질문과 무관한 고정 SQL을 돌려주던 이전
fallback은 제거했다 — 조용한 오답보다 시끄러운 실패가 안전하다.
"""

from __future__ import annotations

import json
import logging
from datetime import date

from app.core.config import get_settings
from app.core.openai_client import get_async_openai_client
from app.logging.performance import log_llm_completion, start_timer
from mcp_servers.data_tools.sales.schema import SchemaResource

logger = logging.getLogger(__name__)

# 추가: 복합질문(예: "올해 매출과 매출 최고 기업")을 여러 개의 독립된 단일 SELECT로
# 쪼갤 때 허용하는 최대 개수. 무제한 허용 시 비용·응답시간이 폭주할 수 있어 하드코딩.
# query.py의 MAX_QUESTION_LENGTH, sql_guard.py의 MAX_LIMIT와 같은 방식으로
# 도메인 파일에 로컬 상수로 둔다.
MAX_SUB_QUERIES = 3

SYSTEM_PROMPT = (
    "당신은 판매 데이터베이스 전용 SQL 생성기입니다. 아래 규칙을 반드시 지키세요.\n"
    "1. 제공된 뷰(view)만 사용하세요. 원본 테이블 이름을 쓰면 권한 오류가 납니다.\n"
    # old: "2. 단일 SELECT 문 하나만 생성하세요. 세미콜론으로 여러 문장을 잇지 마세요.\n"
    # 변경 이유: 복합질문(합계 1건 vs 순위 목록처럼 결과 형태가 다른 질문)을 하나의
    # SELECT로 억지로 합치면 부정확한 SQL이 나와서, 각각 독립된 SELECT로 나누고
    # JSON 배열로 묶어 반환하도록 규칙을 확장했다.
    "2. 질문이 서로 다른 결과 형태(예: 합계 1건 vs 순위 목록)를 동시에 요구하면, "
    f"각각 독립된 단일 SELECT로 나누어 최대 {MAX_SUB_QUERIES}개까지 만드세요. "
    "질문이 하나의 결과 형태만 요구하면 SELECT는 1개만 만드세요. 각 SELECT는 "
    "세미콜론으로 여러 문장을 잇지 말고 하나의 문장이어야 합니다. 최종 출력은 "
    "다음 JSON 형식이어야 합니다: "
    '{"queries": [{"label": "결과를 설명하는 짧은 한글 라벨", "sql": "SELECT ..."}]}\n'
    "3. 결과 건수를 제한하기 위해 LIMIT을 반드시 포함하세요.\n"
    "4. '이번 달', '최근 3개월' 같은 상대 기간은 제공된 오늘 날짜를 기준으로 실제 "
    "날짜(YYYY-MM-DD)로 바꿔 쓰세요. CURDATE()나 NOW()를 쓰지 마세요.\n"
    "5. 지표(매출, 미수금 등)의 정의는 제공된 지표 정의를 그대로 따르세요. 스스로 "
    "다른 컬럼이나 계산식을 만들지 마세요. 특히 '매출'은 고객별·기간별로 묶어도 "
    "항상 v_sales_order.order_amount를 쓰세요. v_sales_order_line은 품목·상품 "
    "단위로 물을 때만 쓰세요.\n"
    "5-1. '2025년'처럼 연도 전체를 물으면 그 해 1월부터 12월까지 전부 포함하세요. "
    "오늘 날짜의 월(月) 숫자로 범위를 제한하지 마세요 — 오늘이 몇 월인지는 과거 "
    "연도의 데이터 범위와 무관합니다.\n"
    "6. 고객의 업종·국가 같은 정보를 상식으로 추측하지 마세요. 데이터에 실제로 적힌 "
    "값만 조건으로 쓰세요.\n"
    "7. SELECT * 를 쓰지 마세요. 필요한 컬럼만 나열하세요.\n"
    "8. 기간을 라벨로 쓸 때는 order_month/invoice_month처럼 이미 문자열로 만들어진 "
    "컬럼을 쓰세요. 직접 DATE_FORMAT을 다시 만들지 마세요.\n"
    "9. 시간 흐름을 보여주는 질문(추이·월별·연도별)은 기간 컬럼 기준 오름차순으로 "
    "ORDER BY 하세요.\n"
    "10. SELECT 목록에서 보여주고 싶은 금액·수량 같은 값 컬럼은 맨 마지막에 두세요.\n"
    "11. 카테고리 비교(고객별, 품목별 등)는 LIMIT 12 이하로, 기간 추이는 LIMIT 60 "
    "이하로 제한하세요.\n"
    "12. 제공된 뷰·지표로 답할 수 없는 질문이면 SQL을 만들지 말고 정확히 다음 한 "
    "줄만 출력하세요: NO_SQL\n"
    "12-1. 질문에 판매 데이터와 무관한 내용(사내 규정, 복리후생 등 문서 관련 질문)이 "
    "함께 섞여 있어도, 판매 데이터로 답할 수 있는 부분이 있으면 그 부분만 골라 SQL을 "
    "만드세요. 무관한 부분이 있다고 질문 전체를 NO_SQL로 처리하지 마세요. 질문 전체가 "
    "판매 데이터와 무관할 때만 NO_SQL을 쓰세요.\n"
    # old: "SQL 코드만 출력하고 다른 설명은 하지 마세요."
    # 변경 이유: 출력이 raw SQL 텍스트가 아니라 2번 규칙의 JSON으로 바뀌었으므로,
    # 최종 지시문도 JSON 출력만 하도록 맞춰야 한다(NO_SQL인 경우는 12번 규칙이 담당).
    "위에서 정한 JSON 형식만 출력하고 다른 설명은 하지 마세요."
)


def _format_schema(schema: SchemaResource) -> str:
    """스키마 Resource를 LLM 프롬프트에 넣을 텍스트로 직렬화한다."""
    views_desc = "\n".join(
        f"- {name}({', '.join(spec['columns'])}): {spec['description']}"
        for name, spec in schema["views"].items()
    )
    metrics_desc = "\n".join(
        f"- {term}: {metric['aggregation']}({metric['view']}.{metric['column']}) {metric['note']}".rstrip()
        for term, metric in schema["metrics"].items()
    )
    coverage = schema["data_coverage"]
    coverage_text = f"{coverage.get('min_order_date') or '?'} ~ {coverage.get('max_order_date') or '?'}"
    return (
        f"[허용된 뷰]\n{views_desc}\n\n"
        f"[지표 정의]\n{metrics_desc}\n\n"
        f"[답할 수 없는 지표] {', '.join(schema['out_of_scope'])}\n\n"
        f"[데이터 보유 기간] {coverage_text}\n"
        f"[통화] {schema['currency']} 단일"
    )


async def _call_llm(user_content: str) -> str:
    """OpenAI를 호출해 SQL 텍스트를 받는다.

    OPENAI_API_KEY가 없으면 예외를 그대로 낸다. mcp_servers/data_tools/server.py가
    이 예외를 QUERY_ERROR로 변환하므로, 조용히 질문과 무관한 SQL을 실행하던 이전
    fallback 방식보다 안전하다(SPEC.md D-16).
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않아 SQL을 생성할 수 없습니다.")

    client = get_async_openai_client(settings.openai_api_key)
    started_ns = start_timer()
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
        # old: max_completion_tokens=400,
        # 변경 이유: 응답이 SELECT 1개짜리 텍스트에서 최대 3개 SELECT를 담은 JSON
        # 배열로 늘어나서, 기존 400 토큰으로는 잘려서 JSON 파싱이 깨질 수 있다.
        max_completion_tokens=900,
        timeout=10,
    )
    log_llm_completion("sales_text2sql", settings.openai_model, started_ns, response)
    text = response.choices[0].message.content or ""
    stripped = text.strip().strip("`")
    # old: return text.strip().strip("`").removeprefix("sql\n").strip()
    # 변경 이유: 출력이 ```sql ... ``` 뿐 아니라 ```json ... ``` 코드펜스로 올 수도
    # 있어서, 두 언어 태그 접두사를 모두 벗겨내야 한다.
    for prefix in ("sql\n", "json\n"):
        if stripped.startswith(prefix):
            stripped = stripped.removeprefix(prefix)
            break
    return stripped.strip()


# old:
# def _extract_sql(raw: str) -> str:
#     """LLM 응답에서 'NO_SQL'이면 빈 문자열로, 아니면 원문 그대로 반환한다."""
#     if raw.strip().upper() == "NO_SQL":
#         return ""
#     return raw
#
# 변경 이유: 응답이 단일 SQL 텍스트에서 최대 MAX_SUB_QUERIES개의 {label, sql} JSON
# 배열로 바뀌어서, NO_SQL이면 빈 리스트를, 아니면 JSON을 파싱해 리스트로 반환하도록
# 교체했다. JSON 파싱에 실패하면 예전처럼 질문과 무관한 SQL을 조용히 반환하지 않고
# 빈 리스트 + 경고 로그를 남긴다.
def _extract_queries(raw: str) -> list[dict[str, str]]:
    """LLM 응답을 파싱한다.

    'NO_SQL'이면 빈 리스트를 반환한다. 그 외에는 `{"queries": [...]}` JSON으로
    간주해 파싱하고, 각 항목에서 label/sql만 뽑아 최대 MAX_SUB_QUERIES개까지
    반환한다. 파싱에 실패하거나 형식이 어긋나면 조용한 오답을 만들지 않기 위해
    빈 리스트를 반환하고 경고 로그를 남긴다.
    """
    stripped = raw.strip()
    if stripped.upper() == "NO_SQL":
        return []
    try:
        payload = json.loads(stripped)
        queries = payload["queries"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("sales text2sql 응답 JSON 파싱 실패: %s / raw=%r", exc, raw)
        return []
    if not isinstance(queries, list):
        logger.warning("sales text2sql queries가 리스트가 아님: %r", queries)
        return []
    return [
        {"label": str(item.get("label", "")), "sql": str(item["sql"])}
        for item in queries[:MAX_SUB_QUERIES]
        if isinstance(item, dict) and item.get("sql")
    ]


async def generate_sql(question: str, schema: SchemaResource) -> list[dict[str, str]]:
    """질문과 오늘 날짜를 스키마 정보와 함께 LLM에 전달해 SELECT SQL 목록을 만든다.

    답할 수 없다고 판단되면 빈 리스트를 반환한다(호출부가 범위 밖으로 처리).
    """
    today = date.today().isoformat()
    user_content = (
        f"{_format_schema(schema)}\n\n[오늘 날짜] {today}\n\n[질문] {question}"
    )
    return _extract_queries(await _call_llm(user_content))


async def generate_sql_with_error(
    question: str,
    schema: SchemaResource,
    failed_sql: str,
    error: str,
) -> list[dict[str, str]]:
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
    return _extract_queries(await _call_llm(user_content))
