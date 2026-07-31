from mcp_servers.data_tools.finance.schema import SchemaResource


async def generate_sql(
    question: str,
    schema: SchemaResource,
) -> str:
    """질문과 제공된 스키마로 SELECT SQL 초안을 생성한다.

    프롬프트는 제공된 테이블·컬럼만 사용하고 단일 SELECT와 결과 건수 제한을 요구한다.
    """
    ...
