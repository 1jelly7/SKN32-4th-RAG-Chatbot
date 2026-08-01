"""구매 질문을 제한된 SELECT 초안으로 변환할 미구현 Text2SQL adapter."""

from mcp_servers.data_tools.purchase.schema import SchemaResource


async def generate_sql(
    question: str,
    schema: SchemaResource,
) -> str:
    """질문과 제공된 스키마로 SELECT SQL 초안을 생성한다.

    프롬프트는 제공된 테이블·컬럼만 사용하고 단일 SELECT와 결과 건수 제한을 요구한다.
    """
    # TODO(implementation): 제공된 구매 schema만 prompt에 넣어 단일 SELECT와 LIMIT을
    # 생성한다. 출력은 신뢰하지 않고 실행 전에 구매 SQL guard가 다시 검증해야 하며,
    # 쓰기/DDL·미허용 table·빈 응답과 정상 집계 질문을 fake LLM으로 검증한다.
    ...
