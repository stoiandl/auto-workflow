import pytest

from auto_workflow.context import get_context


def test_get_context_without_active_run_raises():
    with pytest.raises(RuntimeError):
        _ = get_context()
