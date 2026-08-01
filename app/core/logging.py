import logging


def configure_logging() -> None:
    """요청 ID를 포함한 구조화 로그 형식과 레벨을 한 번만 설정한다.

    질문 원문, 권한, API 키, DB 비밀번호, 전체 근거 본문은 마스킹하거나 기록하지 않는다.
    """
    ...


def get_logger(name: str) -> logging.Logger:
    """모듈명 기반 로거를 반환하며 중복 handler를 추가하지 않는다."""
    ...
