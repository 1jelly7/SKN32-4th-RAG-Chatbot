from __future__ import annotations

from typing import TypedDict


class SQLPolicy(TypedDict):
    allowed_tables: list[str]
    allowed_columns: dict[str, list[str]]
    default_limit: int
    forbidden_keywords: list[str]


def load_sql_policy(policy_path: str) -> SQLPolicy:
    """관리되는 YAML 정책을 읽어 SQL Guard용 allowlist와 제한값을 검증한다.

    allowed_tables/columns, default_limit, forbidden_keywords가 빠졌거나 잘못된 형식이면
    안전한 기본 허용으로 넘어가지 말고 서버 시작을 실패시킨다.
    """
    ...


def validate_sql(sql: str, policy: SQLPolicy) -> str:
    """실행 가능한 안전한 단일 SELECT SQL을 반환하거나 ValueError를 발생시킨다.

    파서 기반으로 INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/GRANT, 다중 statement,
    주석 우회, 미허용 테이블·컬럼을 차단한다. LIMIT가 없으면 정책 default_limit을 추가하고
    과도한 LIMIT는 낮추며, 문자열 치환만으로 보안을 구현하지 않는다.
    """
    ...
