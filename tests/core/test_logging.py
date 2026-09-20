import json
import logging
import sys
from types import TracebackType

from app.core.logging import JsonFormatter, RequestIdFilter, configure_logging
from app.core.middleware import _request_id_ctx_var

_ExcInfo = tuple[type[BaseException], BaseException, TracebackType | None]


def _make_record(msg: str = "hello", exc_info: _ExcInfo | None = None) -> logging.LogRecord:
    return logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=exc_info,
    )


def test_request_id_filter_injects_request_id_when_contextvar_set() -> None:
    token = _request_id_ctx_var.set("abc-123")
    try:
        record = _make_record()
        result = RequestIdFilter().filter(record)
    finally:
        _request_id_ctx_var.reset(token)

    assert result is True
    assert record.request_id == "abc-123"  # type: ignore[attr-defined]


def test_request_id_filter_injects_none_when_contextvar_unset() -> None:
    record = _make_record()

    result = RequestIdFilter().filter(record)

    assert result is True
    assert record.request_id is None  # type: ignore[attr-defined]


def test_json_formatter_produces_valid_json_with_expected_keys() -> None:
    record = _make_record(msg="something happened")
    record.request_id = "req-1"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert payload["message"] == "something happened"
    assert payload["request_id"] == "req-1"
    assert "timestamp" in payload


def test_json_formatter_defaults_request_id_to_none_when_absent() -> None:
    record = _make_record()

    payload = json.loads(JsonFormatter().format(record))

    assert payload["request_id"] is None


def test_json_formatter_includes_exception_when_exc_info_set() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()

    record = _make_record(msg="failure", exc_info=exc_info)  # type: ignore[arg-type]
    record.request_id = None

    payload = json.loads(JsonFormatter().format(record))

    assert "ValueError: boom" in payload["exception"]


def test_json_formatter_omits_exception_key_when_no_exc_info() -> None:
    record = _make_record()
    record.request_id = None

    payload = json.loads(JsonFormatter().format(record))

    assert "exception" not in payload


def test_configure_logging_wires_json_formatter_and_request_id_filter() -> None:
    configure_logging()
    root = logging.getLogger()

    assert any(isinstance(h.formatter, JsonFormatter) for h in root.handlers)
    assert any(isinstance(f, RequestIdFilter) for h in root.handlers for f in h.filters)
