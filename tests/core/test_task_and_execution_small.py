import asyncio

from auto_workflow.execution import _shutdown_pool, get_process_pool
from auto_workflow.task import task


def test_task_decorator_infers_run_in_for_sync():
    @task
    def sync_fn(x: int) -> int:
        return x + 1

    # outside of a flow, call executes immediately via thread to avoid blocking
    assert sync_fn(1) == 2


def test_task_cache_key_uses_default_function():
    @task(cache_ttl=10)
    def f(a: int, b: int = 2) -> int:
        return a + b

    # Using internal API to construct key directly
    key = f.cache_key(1, b=3)
    assert isinstance(key, str) and len(key) == 64


def test_get_process_pool_and_shutdown():
    pool = get_process_pool()
    assert pool is get_process_pool()  # cached
    # ensure shutdown doesn't raise
    _shutdown_pool()
