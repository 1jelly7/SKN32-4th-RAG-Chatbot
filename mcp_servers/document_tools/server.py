from typing import Any


def create_server() -> Any:
    """search_documents 도구를 등록한 Document MCP 서버를 만든다.

    도구 스키마/오류 경계를 정의한다. 내부적으로 문서 DB에서 파일 경로를 조회한 뒤
    파일을 읽지만, 응답에는 내부 파일 경로를 노출하지 않는다.
    """
    ...


def main() -> None:
    """검증된 환경 설정으로 Document MCP 서버를 시작하는 CLI 진입점이다."""
    ...
