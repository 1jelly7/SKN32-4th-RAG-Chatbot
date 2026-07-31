from typing import Any


def create_server() -> Any:
    """도메인 Data MCP 도구와 공통 schema Resource를 등록한다.

    이 진입점은 요청을 재무 또는 판매 도메인 도구로 전달하고 DB 드라이버의 세부 구현은
    외부에 노출하지 않는다.
    """
    ...


def main() -> None:
    """환경 설정을 읽어 Data MCP 서버를 실행하는 CLI 진입점이다."""
    ...
