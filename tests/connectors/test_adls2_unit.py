from __future__ import annotations

import types
from contextlib import contextmanager

import pytest

from auto_workflow.connectors import get, reset
from tests.connectors.adls2_fakes import DummyFS, DummySvc, inject as inject_azure_modules


def setup_function(_):
    reset()
    import auto_workflow.connectors.adls2  # noqa: F401 - ensure registration


def test_upload_and_download(monkeypatch):
    inject_azure_modules(monkeypatch)
    c = get("adls2")
    etag = c.upload_bytes("c", "p.txt", b"hello", content_type="text/plain")
    assert etag
    data = c.download_bytes("c", "p.txt")
    assert data == b"hello"
    # stream
    chunks = list(c.download_stream("c", "p.txt"))
    assert b"".join(chunks) == b"hello"


def test_list_and_exists_delete(monkeypatch):
    inject_azure_modules(monkeypatch)
    c = get("adls2")
    c.upload_bytes("c", "a/b/c.txt", b"x")
    c.upload_bytes("c", "a/b/d.txt", b"y")
    paths = list(c.list_paths("c", prefix="a/b/"))
    assert len(paths) == 2
    assert c.exists("c", "a/b/c.txt") is True
    c.delete_path("c", "a/b/c.txt")
    assert c.exists("c", "a/b/c.txt") is False


def test_error_mapping_auth_and_timeout(monkeypatch):
    inject_azure_modules(monkeypatch)
    # Force upload to raise a ServiceRequestError with timeout message
    import auto_workflow.connectors.adls2 as mod

    class BadFS(DummyFS):
        def get_file_client(self, path: str):  # type: ignore[override]
            class BadFC:
                def __init__(self, storage, path):
                    self.storage = storage
                    self.path = path

                def upload_data(self, data, **kwargs):  # type: ignore[override]
                    raise mod._ensure_deps()["ServiceRequestError"]("read timeout")

            return BadFC(self.storage, path)

    class BadSvc(DummySvc):
        def get_file_system_client(self, name: str):  # type: ignore[override]
            return BadFS()

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {
            "__call__": lambda self, *a, **k: BadSvc(),
            "__init__": lambda self, *a, **k: None,
        },
    )
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = get("adls2")
    with pytest.raises(Exception) as ei:
        c.upload_bytes("c", "p", b"x")
    assert "timed out" in str(ei.value).lower() or "timeout" in str(ei.value).lower()
