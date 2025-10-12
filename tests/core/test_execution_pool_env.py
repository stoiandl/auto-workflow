from auto_workflow.config import reload_config
from auto_workflow.execution import _shutdown_pool, get_process_pool


def test_process_pool_env_digit(monkeypatch):
    monkeypatch.setenv("AUTO_WORKFLOW_PROCESS_POOL_MAX_WORKERS", "2")
    reload_config()
    try:
        pool = get_process_pool()
        assert pool is not None
    finally:
        _shutdown_pool()


def test_process_pool_env_nondigit(monkeypatch):
    monkeypatch.setenv("AUTO_WORKFLOW_PROCESS_POOL_MAX_WORKERS", "abc")
    reload_config()
    try:
        pool = get_process_pool()
        assert pool is not None
    finally:
        _shutdown_pool()
