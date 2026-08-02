"""범용 Data MCP에서 생성 SQL을 실행 전에 제한하려는 정책 스켈레톤."""

from __future__ import annotations

from typing import TypedDict


class SQLPolicy(TypedDict):
    """SELECT 검증에 필요한 allowlist, LIMIT, 금지 키워드 정책."""

    allowed_tables: list[str]
    allowed_columns: dict[str, list[str]]
    default_limit: int
    forbidden_keywords: list[str]


def load_sql_policy(policy_path: str) -> SQLPolicy:
    """관리되는 YAML 정책을 읽어 SQL Guard용 allowlist와 제한값을 검증한다.

    allowed_tables/columns, default_limit, forbidden_keywords가 빠졌거나 잘못된 형식이면
    안전한 기본 허용으로 넘어가지 말고 서버 시작을 실패시킨다.
    """
    # TODO(contract clarification): 정책 파일 형식·소유 경로·parser 의존성을 확정한 뒤
    # 필수 키와 타입을 검증하고 누락 시 fail closed로 기동을 중단한다.
    ...


def validate_sql(sql: str, policy: SQLPolicy) -> str:
    """실행 가능한 안전한 단일 SELECT SQL을 반환하거나 ValueError를 발생시킨다.

    파서 기반으로 INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/GRANT, 다중 statement,
    주석 우회, 미허용 테이블·컬럼을 차단한다. LIMIT가 없으면 정책 default_limit을 추가하고
    과도한 LIMIT는 낮추며, 문자열 치환만으로 보안을 구현하지 않는다.
    """
    # TODO(implementation): 확정된 SQL parser로 단일 SELECT AST, allowlist, LIMIT,
    # 주석·다중 statement 우회를 검증한다. 쓰기/DDL, 미허용 식별자, 정상 집계 SELECT
    # contract test가 완료 조건이다.
    ...
