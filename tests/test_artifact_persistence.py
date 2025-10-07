from auto_workflow import task, flow
from auto_workflow.config import reload_config, DEFAULTS
import os, shutil, json, pathlib

ART_DIR = '.aw_artifacts'

@task(persist=True)
def large():
    return {'k': 'v', 'n': 42}

@task
def consume(ref):
    return ref

@flow
def artifact_flow():
    a = large()
    return consume(a)

def test_filesystem_artifact_roundtrip(tmp_path, monkeypatch):
    # Force filesystem backend
    os.environ['AUTO_WORKFLOW_ARTIFACT_STORE'] = 'filesystem'
    reload_config()
    out = artifact_flow.run()
    # out should be ArtifactRef from consume returning ref
    from auto_workflow.artifacts import ArtifactRef, get_store
    assert hasattr(out, 'key')
    store = get_store()
    val = store.get(out)
    assert val['n'] == 42
    # cleanup env
    del os.environ['AUTO_WORKFLOW_ARTIFACT_STORE']
    reload_config()
