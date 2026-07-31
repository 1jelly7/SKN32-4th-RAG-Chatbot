from typing import Any


def create_server() -> Any:
    """query_business_data 도구와 읽기 전용 schema Resource를 등록한 Data MCP 서버를 만든다.

    도구 스키마/오류 경계를 정의하고 DB 드라이버·정책 파일을 직접 노출하지 않는다.
    """
    ...


def main() -> None:
    """검증된 환경 설정으로 Data MCP 서버를 시작하는 CLI 진입점이다."""
    ...
