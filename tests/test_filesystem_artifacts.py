import os
from pathlib import Path

from auto_workflow import flow, task


@task(persist=True)
def make_data():
    return {"x": 1}


@flow
def fs_flow():
    return make_data()


def test_filesystem_artifact_store(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTO_WORKFLOW_ARTIFACT_STORE", "filesystem")
    monkeypatch.setenv("AUTO_WORKFLOW_ARTIFACT_STORE_PATH", str(tmp_path))
    from auto_workflow.config import reload_config

    reload_config()
    fs_flow.run()
    # verify file exists
    files = list(Path(tmp_path).glob("*"))
    assert files, "artifact file not created"
