"""범용 query_business_data를 공개하려는 미구현 MCP 서버 경계."""

from typing import Any


def create_server() -> Any:
    """query_business_data 도구와 읽기 전용 schema Resource를 등록한 Data MCP 서버를 만든다.

    도구 스키마/오류 경계를 정의하고 DB 드라이버·정책 파일을 직접 노출하지 않는다.
    """
    # TODO(contract clarification): docs/interface.md의 도메인별 Tool 계약과 병존 여부를
    # 확정하기 전에는 새 공개 Tool을 등록하지 않는다. 채택 시 공통 envelope,
    # 인증 context, timeout/error mapping contract test가 필요하다.
    ...


def main() -> None:
    """검증된 환경 설정으로 Data MCP 서버를 시작하는 CLI 진입점이다."""
    # TODO(implementation): create_server 계약 확정 후 설정 검증과 transport 수명주기를
    # 연결하며 import 시 네트워크나 DB 연결을 열지 않는다.
    ...
