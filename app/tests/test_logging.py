"""5필드 한 줄 로그와 handler 중복 방지 계약을 검증한다."""

import logging
from pathlib import Path

from app.logging.formatter import DATE_FORMAT, LOG_FORMAT, EventFormatter
from app.logging.logger import configure_logging


def test_event_formatter_supplies_default_event():
    formatter = EventFormatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )

    assert " | app.test | - | hello" in formatter.format(record)


def test_configure_logging_uses_file_handler_once(tmp_path: Path) -> None:
    log_path = tmp_path / "app.log.txt"
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]

    try:
        root_logger.handlers.clear()
        configure_logging(log_path)
        configure_logging(log_path)

        file_handlers = [
            handler
            for handler in root_logger.handlers
            if isinstance(handler, logging.FileHandler)
        ]
        assert len(file_handlers) == 1
        assert Path(file_handlers[0].baseFilename) == log_path
    finally:
        for handler in root_logger.handlers:
            handler.close()
        root_logger.handlers[:] = original_handlers
