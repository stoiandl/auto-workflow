import pytest

from auto_workflow.artifacts import ArtifactRef, get_store
from auto_workflow.config import reload_config


def test_fs_artifact_missing_file_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_WORKFLOW_ARTIFACT_STORE", "filesystem")
    monkeypatch.setenv("AUTO_WORKFLOW_ARTIFACT_STORE_PATH", str(tmp_path))
    reload_config()
    store = get_store()
    bogus = ArtifactRef(key="does-not-exist")
    with pytest.raises(KeyError):
        store.get(bogus)
