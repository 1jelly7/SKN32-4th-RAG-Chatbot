"""LLM이 만든 SQL을 실행 전에 검사하는 순수 함수 모음 (DB 연결 없음).

3중 방어(뷰 → DB 권한 → 이 가드)의 마지막 층이다. 앞의 두 층이 원본 테이블·PII를
막아주므로, 여기서는 "단일 SELECT인지, 허용된 뷰만 쓰는지, 결과가 너무 크지
않은지"만 확인하면 된다. DB 연결 없이 문자열만 검사하므로 단위 테스트가 쉽다.
"""

from __future__ import annotations

import re

ALLOWED_VIEWS = frozenset(
    {
        "v_sales_order",
        "v_sales_order_line",
        "v_invoice",
        "v_customer",
        "v_sales_order_status",
    }
)

_FORBIDDEN_KEYWORDS = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "REPLACE",
    "MERGE",
    "INTO",
)

_TABLE_REF_PATTERN = re.compile(r"\b(?:FROM|JOIN)\s+`?(\w+)`?", re.IGNORECASE)
_LIMIT_PATTERN = re.compile(r"\bLIMIT\s+(\d+)\b", re.IGNORECASE)

DEFAULT_LIMIT = 200
MAX_LIMIT = 200


def referenced_tables(sql: str) -> set[str]:
    """FROM/JOIN 뒤에 오는 식별자를 뽑아 참조된 테이블·뷰 이름 집합을 만든다."""
    return {m.group(1) for m in _TABLE_REF_PATTERN.finditer(sql)}


def validate_and_normalize(sql: str) -> str:
    """단일 SELECT·허용된 뷰만 참조하는지 검사하고, LIMIT을 200 이하로 맞춘다.

    위반하면 ValueError를 낸다. 주석(``--``, ``/*``, ``#``)이 하나라도 섞여
    있으면 그 안에 무엇을 숨겼는지 파싱해서 판단하지 않고 통째로 거부한다 —
    거부가 통과보다 항상 안전하다.
    """
    stripped = sql.strip()
    normalized = stripped.rstrip(";")

    if (
        ";" in normalized
        or "--" in normalized
        or "/*" in normalized
        or "#" in normalized
    ):
        raise ValueError("단일 SELECT 문만 실행할 수 있습니다.")
    if not (
        normalized.upper().startswith("SELECT") or normalized.upper().startswith("WITH")
    ):
        raise ValueError("SELECT 문만 실행할 수 있습니다.")

    for keyword in _FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", normalized, re.IGNORECASE):
            raise ValueError(f"허용되지 않는 SQL 키워드가 포함되어 있습니다: {keyword}")

    tables = referenced_tables(normalized)
    unknown = tables - ALLOWED_VIEWS
    if unknown:
        raise ValueError(
            f"허용되지 않은 테이블/뷰를 참조합니다: {', '.join(sorted(unknown))}"
        )
    if not tables:
        raise ValueError("FROM 절에서 참조하는 뷰를 찾을 수 없습니다.")

    limit_match = _LIMIT_PATTERN.search(normalized)
    if limit_match is None:
        normalized = f"{normalized} LIMIT {DEFAULT_LIMIT}"
    elif int(limit_match.group(1)) > MAX_LIMIT:
        normalized = _LIMIT_PATTERN.sub(f"LIMIT {MAX_LIMIT}", normalized, count=1)

    return normalized
