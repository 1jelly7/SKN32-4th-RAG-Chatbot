from typing import Any


def create_server() -> Any:
    """search_documents 도구만 공개하는 Document MCP 서버를 구성한다.

    도구 입력/출력 스키마, 오류 매핑, 서버 수명 관리를 등록하고 FAISS 내부 구현을 외부에
    노출하지 않는다.
    """
    ...


def main() -> None:
    """환경 설정을 읽어 Document MCP 서버를 실행하는 CLI 진입점이다."""
    ...
