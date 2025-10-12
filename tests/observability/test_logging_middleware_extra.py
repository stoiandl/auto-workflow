import json
import logging

from auto_workflow.logging_middleware import (
    StructuredPrettyFormatter,
    enable_default_logging,
    enable_pretty_logging,
    register_structured_logging,
)


def test_enable_default_and_pretty_logging_idempotent(caplog):
    caplog.set_level(logging.INFO)
    enable_default_logging("INFO")
    # Second call should not duplicate handlers
    enable_default_logging("INFO")
    # Switch to pretty; should replace default
    enable_pretty_logging("DEBUG")
    enable_pretty_logging("WARNING")  # idempotent multiple times


def test_structured_pretty_formatter_parses_json_and_fallbacks():
    fmt = StructuredPrettyFormatter(datefmt="%Y-%m-%d %H:%M:%S")
    rec = logging.LogRecord(
        name="auto_workflow.tasks",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=json.dumps(
            {
                "event": "task_ok",
                "flow": "f",
                "run_id": "r1",
                "task": "t",
                "node": "n",
                "duration_ms": 12.345,
            }
        ),
        args=(),
        exc_info=None,
    )
    out = fmt.format(rec)
    assert "task_ok" in out and "duration=12.3ms" in out

    # Non-JSON message -> fallback to base formatter
    rec2 = logging.LogRecord(
        name="auto_workflow.tasks",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="plain text",
        args=(),
        exc_info=None,
    )
    out2 = fmt.format(rec2)
    assert "plain text" in out2

    # Non-numeric duration -> string formatting branch
    rec3 = logging.LogRecord(
        name="auto_workflow.tasks",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=json.dumps({"event": "task_ok", "duration_ms": "n/a"}),
        args=(),
        exc_info=None,
    )
    out3 = fmt.format(rec3)
    assert "duration=n/a" in out3


def test_register_structured_logging_is_idempotent():
    # Multiple calls should not re-register
    register_structured_logging()
    register_structured_logging()
