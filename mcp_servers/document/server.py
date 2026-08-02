"""ACL 기반 별도 Document MCP transport의 미구현 서버 진입점."""

from typing import Any


def create_server() -> Any:
    """search_documents 도구만 공개하는 Document MCP 서버를 구성한다.

    도구 입력/출력 스키마, 오류 매핑, 서버 수명 관리를 등록하고 FAISS 내부 구현을 외부에
    노출하지 않는다.
    """
    # TODO(contract clarification): document_tools 서버와 이 서버 중 공식 transport 및
    # user_context schema를 정한 뒤 등록한다. envelope, NO_RESULT, file_path 비노출
    # contract test가 완료 조건이다.
    ...


def main() -> None:
    """환경 설정을 읽어 Document MCP 서버를 실행하는 CLI 진입점이다."""
    # TODO(implementation): 서버 계약 확정 후 설정 검증과 resource cleanup을 연결하며
    # import만으로 외부 연결을 열지 않는다.
    ...
