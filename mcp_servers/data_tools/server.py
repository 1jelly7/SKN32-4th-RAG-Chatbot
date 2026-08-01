"""구매·판매 Data MCP Tool을 공통 envelope로 공개할 서버 경계.

도메인 모듈의 Text2SQL·MySQL 세부 구현을 숨기고 SELECT 전용 호출만 등록해야 한다.
현재 서버 조립은 미구현이며 이 파일을 import해도 transport가 시작되지는 않는다.
"""

from typing import Any


def create_server() -> Any:
    """도메인 Data MCP 도구와 공통 schema Resource를 등록한다.

    이 진입점은 요청을 구매 또는 판매 도메인 도구로 전달하고 DB 드라이버의 세부 구현은
    외부에 노출하지 않는다. 자연어 구매·판매 조회에만 사용하며 ETL이나 쓰기 작업에는
    사용하지 않는다. 각 Tool은 ``docs/interface.md``의 success/error envelope를 반환해야
    한다.
    """
    # TODO(implementation): MCP server에 query_purchase/query_sales와 읽기 전용 schema
    # Resource를 등록하고 도메인 서비스의 evidence 목록을 공통 ToolEnvelope로 변환한다.
    # NO_RESULT, QUERY_ERROR, malformed 내부 결과, timeout을 서로 구분하며 SQL이나 연결
    # 정보를 envelope에 노출하지 않는다.
    # Completion criteria:
    # - Tool 이름과 domain이 docs/interface.md 계약과 일치한다.
    # - Data MCP 경로에서 SELECT 외 SQL과 ETL 호출이 불가능하다.
    # - purchase/sales 성공·빈 결과·query error의 fake contract test가 통과한다.
    ...


def main() -> None:
    """환경 설정을 읽어 Data MCP 서버를 실행하는 CLI 진입점이다."""
    # TODO(implementation): 검증된 설정으로 create_server() 결과를 시작하고 종료 시
    # transport 자원을 정리한다. 설정 오류는 자격증명 없이 기동 단계에서 보고한다.
    ...
