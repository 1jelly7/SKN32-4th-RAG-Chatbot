import logging
from pathlib import Path

from app.logging.formatter import DATE_FORMAT, LOG_FORMAT, EventFormatter


def configure_logging() -> None:
    """요청 ID를 포함한 구조화 로그 형식과 레벨을 한 번만 설정한다.

    질문 원문, API 키, DB 비밀번호, 전체 근거 본문은 마스킹하거나 기록하지 않는다.
    """
    log_path = Path("logs/app.log.txt")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    resolved_log_path = log_path.resolve()
    has_app_handler = any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename).resolve() == resolved_log_path
        for handler in root_logger.handlers
    )
    if not has_app_handler:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(EventFormatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """모듈명 기반 로거를 반환하며 중복 handler를 추가하지 않는다."""
    return logging.getLogger(name)
