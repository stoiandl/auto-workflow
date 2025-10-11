from auto_workflow.lifecycle import shutdown
from auto_workflow.artifacts import FileSystemArtifactStore, ArtifactRef
from auto_workflow.config import reload_config


def test_lifecycle_shutdown_idempotent():
    shutdown()
    shutdown()  # should not raise


def test_artifacts_json_serializer_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_WORKFLOW_ARTIFACT_SERIALIZER", "json")
    reload_config()
    s = FileSystemArtifactStore(tmp_path)
    val = {"a": 1, "b": [1, 2, 3]}
    ref = s.put(val)
    out = s.get(ArtifactRef(ref.key))
    assert out == val
