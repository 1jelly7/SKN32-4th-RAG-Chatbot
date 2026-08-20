"""통합 담당자가 소유하는 공통 로그 인터페이스."""

from app.logging.logger import configure_logging, get_logger

__all__ = ["configure_logging", "get_logger"]
