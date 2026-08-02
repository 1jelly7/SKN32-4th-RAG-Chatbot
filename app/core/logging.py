"""향후 구조화 logging facade를 위한 미구현 호환 경계.

현재 실제 앱 factory는 ``app.logging`` 패키지의 구현을 주입받는다. 두 경계의 통합
방향이 확정되기 전에는 이 스켈레톤을 운영 구현처럼 사용하지 않는다.
"""

import logging


def configure_logging() -> None:
    """요청 ID를 포함한 구조화 로그 형식과 레벨을 한 번만 설정한다.

    질문 원문, 권한, API 키, DB 비밀번호, 전체 근거 본문은 마스킹하거나 기록하지 않는다.
    """
    # TODO(contract clarification): ``app.logging.logger``와 이 facade 중 단일 공개
    # 진입점을 정한다. 구현 시 5필드 한 줄 포맷, handler 중복 방지, 질문 원문·근거·
    # 자격증명 비기록을 동일 contract test로 보장해야 한다.
    ...


def get_logger(name: str) -> logging.Logger:
    """모듈명 기반 로거를 반환하며 중복 handler를 추가하지 않는다."""
    # TODO(implementation): facade 채택 시 표준 logger를 반환하되 handler를 추가하거나
    # import 시 파일을 열지 않는다.
    ...
