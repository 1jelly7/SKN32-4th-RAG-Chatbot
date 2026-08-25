"""소유권 문서의 한 줄 1이벤트 로그 포맷을 정의한다."""

import logging

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(event)s | %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


class EventFormatter(logging.Formatter):
    """event가 없는 표준 로그에도 안전한 기본값을 넣는 공통 포매터."""

    def format(self, record: logging.LogRecord) -> str:
        """event 필드가 없는 third-party record도 공통 5필드 형식으로 변환한다."""
        if not hasattr(record, "event"):
            record.event = "-"
        return super().format(record)
