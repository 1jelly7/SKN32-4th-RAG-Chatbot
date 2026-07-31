import logging

from app.logging.formatter import DATE_FORMAT, LOG_FORMAT, EventFormatter


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
