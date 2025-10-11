import os
import time
from pathlib import Path

from auto_workflow import flow, task
from auto_workflow.config import reload_config


@task(cache_ttl=2)
def compute(v: int):
    return v * 2


@flow
def cached_flow(v: int):
    a = compute(v)
    b = compute(v)
    return a, b


def test_filesystem_result_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_WORKFLOW_RESULT_CACHE", "filesystem")
    monkeypatch.setenv("AUTO_WORKFLOW_RESULT_CACHE_PATH", str(tmp_path))
    reload_config()
    out1 = cached_flow.run(5)
    assert out1 == (10, 10)
    # should have one file
    assert list(Path(tmp_path).glob("*"))
    time.sleep(0.1)
    out2 = cached_flow.run(5)
    assert out2 == (10, 10)
