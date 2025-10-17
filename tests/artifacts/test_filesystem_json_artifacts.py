import os
from pathlib import Path

from auto_workflow.artifacts import ArtifactRef, get_store
from auto_workflow.config import reload_config


def test_filesystem_artifact_store_json_serializer(tmp_path, monkeypatch):
    # Configure FS backend with JSON serializer
    monkeypatch.setenv("AUTO_WORKFLOW_ARTIFACT_STORE", "filesystem")
    monkeypatch.setenv("AUTO_WORKFLOW_ARTIFACT_STORE_PATH", str(tmp_path))
    monkeypatch.setenv("AUTO_WORKFLOW_ARTIFACT_SERIALIZER", "json")
    reload_config()
    store = get_store()
    payload = {"a": 1, "b": [1, 2, 3]}
    ref = store.put(payload)
    assert isinstance(ref, ArtifactRef)
    loaded = store.get(ref)
    assert loaded == payload
    # Ensure file exists and is not empty
    p = Path(tmp_path) / ref.key
    assert p.exists() and p.stat().st_size > 0
