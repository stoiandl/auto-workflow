import os

from auto_workflow.artifacts import FileSystemArtifactStore, ArtifactRef


def test_filesystem_artifact_store_pickle(tmp_path, monkeypatch):
    # ensure pickle serializer
    monkeypatch.setenv("AUTO_WORKFLOW_ARTIFACT_SERIALIZER", "pickle")
    store = FileSystemArtifactStore(tmp_path)
    ref = store.put({"a": 1})
    out = store.get(ref)
    assert out == {"a": 1}


def test_filesystem_artifact_store_json(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_WORKFLOW_ARTIFACT_SERIALIZER", "json")
    store = FileSystemArtifactStore(tmp_path)
    ref = store.put({"b": 2})
    out = store.get(ref)
    assert out == {"b": 2}
