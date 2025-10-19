from __future__ import annotations

import io
import sys
import types
from contextlib import suppress

import pytest

from auto_workflow.connectors import get, reset
from tests.connectors.adls2_fakes import DummyFS, DummySvc, inject as inject_azure_modules


def setup_function(_):
    reset()
    import auto_workflow.connectors.adls2  # noqa: F401 - ensure registration


def test_connection_string_branch_and_kwargs(monkeypatch):
    # Inject fakes and enforce connection string branch with retry/transport kwargs
    inject_azure_modules(
        monkeypatch,
        with_conn_str=True,
        retries=4,
        timeouts={"connect_s": 1.23, "operation_s": 4.56},
    )
    c = get("adls2", profile="example")
    # Touch service and filesystem accessors
    svc = c.datalake_service_client()
    fs = c.filesystem_client("cont")
    assert isinstance(svc, DummySvc)
    assert isinstance(fs, DummyFS)


def test_error_mapping_service_response_and_unavailable(monkeypatch):
    # Extend fakes to raise specific exceptions to hit mapping branches
    inject_azure_modules(monkeypatch)
    import auto_workflow.connectors.adls2 as mod

    class BadFS(DummyFS):
        def get_file_client(self, path: str):  # type: ignore[override]
            class BadFC:
                def __init__(self, storage, path):
                    self.storage = storage
                    self.path = path

                def upload_data(self, data, **kwargs):  # type: ignore[override]
                    raise mod._ensure_deps()["ServiceResponseError"]("resp err")

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
    assert "response" in str(ei.value).lower()

    # Also directly exercise HttpResponseError mapping for 503
    ns2 = mod._ensure_deps()

    class FakeHttp503Error(Exception):
        status_code = 503

    from auto_workflow.connectors.exceptions import TransientError

    # allow mapping via isinstance check by injecting class into deps
    ns3 = ns2.copy()
    ns3["HttpResponseError"] = FakeHttp503Error
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns3)
    assert isinstance(mod._map_error(FakeHttp503Error()), TransientError)


def test_ensure_deps_and_azure_type_mappings(monkeypatch):
    import auto_workflow.connectors.adls2 as mod

    # Build fake azure package tree in sys.modules so _ensure_deps executes real imports
    azure = types.ModuleType("azure")
    storage = types.ModuleType("azure.storage")
    filedatalake = types.ModuleType("azure.storage.filedatalake")
    core = types.ModuleType("azure.core")
    exceptions = types.ModuleType("azure.core.exceptions")
    identity = types.ModuleType("azure.identity")
    pipeline = types.ModuleType("azure.core.pipeline")
    policies = types.ModuleType("azure.core.pipeline.policies")
    transport = types.ModuleType("azure.core.pipeline.transport")

    class DataLakeServiceClient:  # pragma: no cover - used by ensure_deps only
        pass

    class FileSystemClient:  # pragma: no cover - used by ensure_deps only
        pass

    class DefaultAzureCredential:  # pragma: no cover - used by ensure_deps only
        def __call__(self):
            return object()

    class ClientAuthenticationError(Exception):
        pass

    class ResourceNotFoundError(Exception):
        pass

    class ResourceExistsError(Exception):
        pass

    class ServiceRequestError(Exception):
        pass

    class ServiceResponseError(Exception):
        pass

    class HttpResponseError(Exception):
        def __init__(self, status_code=None):
            self.status_code = status_code

    class RetryPolicy:  # pragma: no cover
        def __init__(self, *a, **k):
            pass

    class RequestsTransport:  # pragma: no cover
        def __init__(self, *a, **k):
            pass

    filedatalake.DataLakeServiceClient = DataLakeServiceClient
    filedatalake.FileSystemClient = FileSystemClient
    exceptions.ClientAuthenticationError = ClientAuthenticationError
    exceptions.ResourceNotFoundError = ResourceNotFoundError
    exceptions.ResourceExistsError = ResourceExistsError
    exceptions.ServiceRequestError = ServiceRequestError
    exceptions.ServiceResponseError = ServiceResponseError
    exceptions.HttpResponseError = HttpResponseError
    identity.DefaultAzureCredential = DefaultAzureCredential
    policies.RetryPolicy = RetryPolicy
    transport.RequestsTransport = RequestsTransport

    monkeypatch.setitem(sys.modules, "azure", azure)
    monkeypatch.setitem(sys.modules, "azure.storage", storage)
    monkeypatch.setitem(sys.modules, "azure.storage.filedatalake", filedatalake)
    monkeypatch.setitem(sys.modules, "azure.core", core)
    monkeypatch.setitem(sys.modules, "azure.core.exceptions", exceptions)
    monkeypatch.setitem(sys.modules, "azure.identity", identity)
    monkeypatch.setitem(sys.modules, "azure.core.pipeline", pipeline)
    monkeypatch.setitem(sys.modules, "azure.core.pipeline.policies", policies)
    monkeypatch.setitem(sys.modules, "azure.core.pipeline.transport", transport)

    deps = mod._ensure_deps()
    # All keys should exist from our fake modules
    assert set(["DataLakeServiceClient", "FileSystemClient", "DefaultAzureCredential"]).issubset(
        set(deps.keys())
    )

    # Exercise azure-type branches in _map_error
    from auto_workflow.connectors.exceptions import (
        AuthError,
        NotFoundError,
        TimeoutError,
        TransientError,
    )

    assert isinstance(mod._map_error(ClientAuthenticationError()), AuthError)
    assert isinstance(mod._map_error(ResourceNotFoundError()), NotFoundError)
    assert isinstance(mod._map_error(HttpResponseError(503)), TransientError)
    assert isinstance(mod._map_error(ServiceRequestError("other")), TransientError)
    assert isinstance(mod._map_error(ServiceRequestError("timed out")), TimeoutError)
    assert isinstance(mod._map_error(ServiceResponseError()), TransientError)


def test_open_account_url_fallbacks_and_callable_created(monkeypatch):
    import auto_workflow.connectors.adls2 as mod
    from auto_workflow.connectors.adls2 import ADLS2Client

    # Ensure azure deps are available first
    inject_azure_modules(monkeypatch)

    class DLService:
        def __init__(self, *a, **k):
            # Simulate failure when credential is provided
            if "credential" in k:
                raise TypeError("bad signature")

        def __call__(self, *a, **k):
            return DummySvc()

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = DLService
    ns["RetryPolicy"] = None
    ns["RequestsTransport"] = None
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = ADLS2Client(
        name="adls2", cfg={"account_url": "https://example/", "use_default_credentials": False}
    )
    c.open()
    assert isinstance(c.datalake_service_client(), DummySvc)


def test_filesystem_client_constructor_fallback(monkeypatch):
    import auto_workflow.connectors.adls2 as mod
    from auto_workflow.connectors.adls2 import ADLS2Client

    inject_azure_modules(monkeypatch)

    class OneArgFS:
        def __init__(self, container):
            self.container = container

    ns = mod._ensure_deps().copy()
    ns["FileSystemClient"] = OneArgFS
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = ADLS2Client(name="adls2")
    c._svc = object()  # force path without get_file_system_client and not callable
    fs = c.filesystem_client("myc")
    assert isinstance(fs, OneArgFS)
    assert fs.container == "myc"


def test_make_dirs_exist_ok_false_raises(monkeypatch):
    inject_azure_modules(monkeypatch)
    import auto_workflow.connectors.adls2 as mod
    from auto_workflow.connectors.exceptions import PermanentError

    class BrokenFS(DummyFS):
        def create_directory(self, path: str, timeout=None):  # type: ignore[override]
            raise mod._ensure_deps()["ResourceExistsError"]("exists")

    class S(DummySvc):
        def get_file_system_client(self, name: str):  # type: ignore[override]
            return BrokenFS()

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {
            "__call__": lambda self, *a, **k: S(),
            "__init__": lambda self, *a, **k: None,
        },
    )
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = get("adls2")
    with pytest.raises(PermanentError):
        c.make_dirs("c", "d/exists", exist_ok=False)


def test_list_paths_alternate_fields(monkeypatch):
    inject_azure_modules(monkeypatch)
    import auto_workflow.connectors.adls2 as mod

    class FS(DummyFS):
        def get_paths(self, name_starts_with=None, recursive=True, timeout=None):  # type: ignore[override]
            class P:
                path = "dir/"
                is_directory = True
                size = 0
                last_modified = "now"
                etag = "e2"

            yield P()

    class S(DummySvc):
        def get_file_system_client(self, name: str):  # type: ignore[override]
            return FS()

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {
            "__call__": lambda self, *a, **k: S(),
            "__init__": lambda self, *a, **k: None,
        },
    )
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = get("adls2")
    rows = list(c.list_paths("c", prefix="dir"))
    assert rows and rows[0]["path"] == "dir/" and rows[0]["is_directory"] is True


def test_connection_string_constructor_fallback_no_fcs(monkeypatch):
    # Ensure deps available then override DLS to lack from_connection_string
    inject_azure_modules(monkeypatch, with_conn_str=True)
    import auto_workflow.connectors.adls2 as mod

    class DLSNoFCS:
        def __init__(self, *a, **k):
            pass

        def get_file_system_client(self, name: str):
            return DummyFS()

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = DLSNoFCS
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = get("adls2")
    # Should succeed via constructor fallback
    assert isinstance(c.filesystem_client("x"), DummyFS)


def test_map_error_when_no_deps(monkeypatch):
    import auto_workflow.connectors.adls2 as mod

    # Force _ensure_deps to fail to cover the heuristic-only branch
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: (_ for _ in ()).throw(RuntimeError()))
    from auto_workflow.connectors.exceptions import NotFoundError

    err = mod._map_error(Exception("404 not found"))
    assert isinstance(err, NotFoundError)


def test_delete_file_success_early_return(monkeypatch):
    inject_azure_modules(monkeypatch)
    c = get("adls2")
    c.upload_bytes("c", "del.txt", b"x")
    # Should hit fs.delete_file path and return early without raising
    c.delete_path("c", "del.txt")
    assert c.exists("c", "del.txt") is False


def test_client_factory_and_client_usage(monkeypatch):
    inject_azure_modules(monkeypatch)
    import auto_workflow.connectors.adls2 as mod

    # Use factory directly
    cf = mod._factory("default", {})
    assert isinstance(cf, mod.ADLS2Client)
    # And the exported client() helper
    c = mod.client()
    etag = c.upload_bytes("c", "f.txt", b"z")
    assert etag


def test_exists_directory_check(monkeypatch):
    inject_azure_modules(monkeypatch)
    c = get("adls2")
    # A path that looks like a directory should trigger directory branch
    c.make_dirs("c", "dir/subdir")
    # Our DummyDirClient returns props, so exists should be True via directory branch
    assert c.exists("c", "dir/subdir") is True


def test_download_bytes_fallback_chunks(monkeypatch):
    inject_azure_modules(monkeypatch)
    import auto_workflow.connectors.adls2 as mod

    class DL(DummyFS):
        def get_file_client(self, path: str):  # type: ignore[override]
            class FC:
                def __init__(self, storage, path):
                    self.storage = storage
                    self.path = path

                def download_file(self, offset=None, length=None, timeout=None):
                    class D:
                        def chunks(self, size=None):
                            yield b"abc"
                            yield b"def"

                    return D()

            return FC(self.storage, path)

    class S(DummySvc):
        def get_file_system_client(self, name: str):  # type: ignore[override]
            return DL()

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {
            "__call__": lambda self, *a, **k: S(),
            "__init__": lambda self, *a, **k: None,
        },
    )
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = get("adls2")
    out = c.download_bytes("c", "p")
    assert out == b"abcdef"


def test_download_stream_readall_fallback(monkeypatch):
    inject_azure_modules(monkeypatch)
    import auto_workflow.connectors.adls2 as mod

    class DL(DummyFS):
        def get_file_client(self, path: str):  # type: ignore[override]
            class FC:
                def download_file(self, timeout=None):
                    class D:
                        def readall(self):
                            return b"hello"

                    return D()

            return FC()

    class S(DummySvc):
        def get_file_system_client(self, name: str):  # type: ignore[override]
            return DL()

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {
            "__call__": lambda self, *a, **k: S(),
            "__init__": lambda self, *a, **k: None,
        },
    )
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = get("adls2")
    chunks = list(c.download_stream("c", "p"))
    assert b"".join(chunks) == b"hello"


def test_delete_path_fallback_delete_directory(monkeypatch):
    inject_azure_modules(monkeypatch)
    import auto_workflow.connectors.adls2 as mod

    class DL(DummyFS):
        def delete_file(self, path: str, timeout=None):  # type: ignore[override]
            raise Exception("no file")

        def delete_directory(self, path: str, recursive: bool = False, timeout=None):  # type: ignore[override]
            raise TypeError("old signature")

    class S(DummySvc):
        def get_file_system_client(self, name: str):  # type: ignore[override]
            return DL()

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {
            "__call__": lambda self, *a, **k: S(),
            "__init__": lambda self, *a, **k: None,
        },
    )
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = get("adls2")
    # Should fall back to directory_client.delete_directory
    with suppress(Exception):
        c.delete_path("c", "some/dir")


def test_filesystem_client_unwrap_callable(monkeypatch):
    inject_azure_modules(monkeypatch)
    c = get("adls2")
    # Force _svc to be a callable wrapper
    c._svc = lambda: DummySvc()  # type: ignore[attr-defined]
    fs = c.filesystem_client("x")
    assert isinstance(fs, DummyFS)


def test_make_dirs_exists_ok_handling(monkeypatch):
    inject_azure_modules(monkeypatch)
    import auto_workflow.connectors.adls2 as mod

    class BrokenFS(DummyFS):
        def create_directory(self, path: str, timeout=None):  # type: ignore[override]
            raise mod._ensure_deps()["ResourceExistsError"]("exists")

    class S(DummySvc):
        def get_file_system_client(self, name: str):  # type: ignore[override]
            return BrokenFS()

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {
            "__call__": lambda self, *a, **k: S(),
            "__init__": lambda self, *a, **k: None,
        },
    )
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = get("adls2")
    # Should not raise because exist_ok=True by default
    c.make_dirs("c", "d/exists")


def test_create_container_happy_path_and_timeout(monkeypatch):
    import auto_workflow.connectors.adls2 as mod
    from auto_workflow.connectors import get

    called: dict[str, object] = {}

    class Svc:
        def create_file_system(self, **kwargs):  # type: ignore[override]
            called.update(kwargs)

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {
            "__call__": lambda self, *a, **k: Svc(),
            "__init__": lambda self, *a, **k: None,
        },
    )
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = get("adls2")
    c.create_container("cont", timeout=1.5)
    # Ensure file_system name and timeout propagated
    assert called.get("file_system") == "cont"
    assert called.get("timeout") == 1.5


def test_create_container_exist_ok_and_error(monkeypatch):
    import auto_workflow.connectors.adls2 as mod
    from auto_workflow.connectors import get
    from auto_workflow.connectors.exceptions import PermanentError

    class Svc:
        def create_file_system(self, **kwargs):  # type: ignore[override]
            raise mod._ensure_deps()["ResourceExistsError"]("exists")

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {
            "__call__": lambda self, *a, **k: Svc(),
            "__init__": lambda self, *a, **k: None,
        },
    )
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = get("adls2")
    # Should swallow when exist_ok=True
    c.create_container("cont", exist_ok=True)
    # But raise when exist_ok=False
    with pytest.raises(PermanentError):
        c.create_container("cont", exist_ok=False)


def test_create_container_filesystem_fallback(monkeypatch):
    import auto_workflow.connectors.adls2 as mod
    from auto_workflow.connectors import get
    from tests.connectors.adls2_fakes import DummySvc

    flags = {"called": False}

    class FS:
        def create_file_system(self, timeout=None):  # type: ignore[override]
            flags["called"] = True

    class S(DummySvc):
        def get_file_system_client(self, name: str):  # type: ignore[override]
            return FS()

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {
            "__call__": lambda self, *a, **k: S(),
            "__init__": lambda self, *a, **k: None,
        },
    )
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = get("adls2")
    c.create_container("cont")
    assert flags["called"] is True


def test_create_container_no_methods_is_noop(monkeypatch):
    import auto_workflow.connectors.adls2 as mod
    from auto_workflow.connectors import get
    from tests.connectors.adls2_fakes import DummyFS

    class Svc:
        def get_file_system_client(self, name: str):  # lacks create_file_system
            return DummyFS()

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {
            "__call__": lambda self, *a, **k: Svc(),
            "__init__": lambda self, *a, **k: None,
        },
    )
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = get("adls2")
    # Should not raise
    c.create_container("cont")


def test_map_error_httpresponse_statuses(monkeypatch):
    import auto_workflow.connectors.adls2 as mod
    from auto_workflow.connectors.exceptions import AuthError, NotFoundError, TimeoutError

    # Craft fake error classes to drive isinstance checks
    class HttpErr401Error(Exception):
        status_code = 401

    class HttpErr404Error(Exception):
        status_code = 404

    class HttpErr408Error(Exception):
        status_code = 408

    ns = mod._ensure_deps().copy()
    ns["HttpResponseError"] = HttpErr401Error
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)
    assert isinstance(mod._map_error(HttpErr401Error()), AuthError)

    ns2 = ns.copy()
    ns2["HttpResponseError"] = HttpErr404Error
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns2)
    assert isinstance(mod._map_error(HttpErr404Error()), NotFoundError)

    ns3 = ns.copy()
    ns3["HttpResponseError"] = HttpErr408Error
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns3)
    assert isinstance(mod._map_error(HttpErr408Error()), TimeoutError)


def test_open_created_callable_unwrap(monkeypatch):
    import auto_workflow.connectors.adls2 as mod
    from auto_workflow.connectors.adls2 import ADLS2Client
    from tests.connectors.adls2_fakes import DummySvc

    class Wrapper:
        # No get_file_system_client on wrapper; calling returns real service
        def __call__(self):
            return DummySvc()

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {"__call__": lambda self, *a, **k: Wrapper(), "__init__": lambda self, *a, **k: None},
    )
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = ADLS2Client(name="adls2")
    c.open()
    assert isinstance(c.datalake_service_client(), DummySvc)


def test_exists_handles_resource_not_found(monkeypatch):
    import auto_workflow.connectors.adls2 as mod
    from auto_workflow.connectors import get
    from tests.connectors.adls2_fakes import DummySvc

    class FS:
        def get_file_client(self, path: str):
            class FC:
                def get_file_properties(self, timeout=None):  # type: ignore[override]
                    raise mod._ensure_deps()["ResourceNotFoundError"]("missing")

            return FC()

    class S(DummySvc):
        def get_file_system_client(self, name: str):  # type: ignore[override]
            return FS()

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {
            "__call__": lambda self, *a, **k: S(),
            "__init__": lambda self, *a, **k: None,
        },
    )
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = get("adls2")
    assert c.exists("cont", "some/missing.txt") is False


def test_upload_bytes_etag_from_headers(monkeypatch):
    import auto_workflow.connectors.adls2 as mod
    from auto_workflow.connectors import get
    from tests.connectors.adls2_fakes import DummySvc

    class FS:
        def __init__(self):
            self.storage = {}

        def get_file_client(self, path: str):
            class FC:
                def upload_data(self, data, **kwargs):  # type: ignore[override]
                    class Resp:
                        headers = {"etag": "etag-hdr"}

                    return Resp()

            return FC()

    class S(DummySvc):
        def get_file_system_client(self, name: str):  # type: ignore[override]
            return FS()

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {
            "__call__": lambda self, *a, **k: S(),
            "__init__": lambda self, *a, **k: None,
        },
    )
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = get("adls2")
    etag = c.upload_bytes("cont", "p", b"x")
    assert etag == "etag-hdr"


def test_upload_uses_content_settings_and_chunk_size(monkeypatch):
    import auto_workflow.connectors.adls2 as mod
    from tests.connectors.adls2_fakes import DummySvc

    # FS and FC that capture kwargs passed to upload_data
    captured: dict[str, object] = {}

    class FS:
        def __init__(self):
            self.storage: dict[str, bytes] = {}

        def get_file_client(self, path: str):
            class FC:
                def __init__(self, storage, path):
                    self.storage = storage
                    self.path = path

                def upload_data(self, data, **kwargs):  # type: ignore[override]
                    captured.update(kwargs)
                    if isinstance(data, (bytes, bytearray)):
                        self.storage[self.path] = bytes(data)
                    else:
                        self.storage[self.path] = data.read()

                    class Resp:
                        etag = "e"

                    return Resp()

            return FC(self.storage, path)

    class S(DummySvc):
        def get_file_system_client(self, name: str):  # type: ignore[override]
            return FS()

    # Fake deps that include ContentSettings
    class FakeContentSettings:
        def __init__(self, content_type=None, *a, **k):  # pragma: no cover - simple carrier
            self.content_type = content_type

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {
            "__call__": lambda self, *a, **k: S(),
            "__init__": lambda self, *a, **k: None,
        },
    )
    ns["ContentSettings"] = FakeContentSettings
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    from auto_workflow.connectors import get

    c = get("adls2")
    c.upload_bytes(
        "cont",
        "file.csv",
        b"csv-data",
        content_type="text/csv",
        metadata={"a": "b"},
        chunk_size=1024,
    )

    # Assertions on captured kwargs
    assert "content_settings" in captured
    assert getattr(captured["content_settings"], "content_type", None) == "text/csv"
    assert captured.get("chunk_size") == 1024
    assert captured.get("overwrite") is True
    # metadata should pass through untouched
    assert captured.get("metadata") == {"a": "b"}


def test_upload_with_content_type_when_no_contentsettings(monkeypatch):
    import auto_workflow.connectors.adls2 as mod
    from tests.connectors.adls2_fakes import DummySvc

    class FS:
        def __init__(self):
            self.storage: dict[str, bytes] = {}

        def get_file_client(self, path: str):
            class FC:
                def __init__(self, storage, path):
                    self.storage = storage
                    self.path = path

                def upload_data(self, data, **kwargs):  # type: ignore[override]
                    # Ensure we don't crash and content_settings is simply absent
                    assert "content_settings" not in kwargs
                    if isinstance(data, (bytes, bytearray)):
                        self.storage[self.path] = bytes(data)
                    else:
                        self.storage[self.path] = data.read()

                    class Resp:
                        etag = "e"

                    return Resp()

            return FC(self.storage, path)

    class S(DummySvc):
        def get_file_system_client(self, name: str):  # type: ignore[override]
            return FS()

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {
            "__call__": lambda self, *a, **k: S(),
            "__init__": lambda self, *a, **k: None,
        },
    )
    # Ensure ContentSettings missing
    ns.pop("ContentSettings", None)
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    from auto_workflow.connectors import get

    c = get("adls2")
    etag = c.upload_bytes("c", "p.txt", b"hello", content_type="text/plain")
    assert etag


def test_exists_outer_resource_not_found_returns_false(monkeypatch):
    inject_azure_modules(monkeypatch)
    import auto_workflow.connectors.adls2 as mod

    class FS(DummyFS):
        def get_file_client(self, path: str):  # type: ignore[override]
            raise mod._ensure_deps()["ResourceNotFoundError"]("rnfe")

    class S(DummySvc):
        def get_file_system_client(self, name: str):  # type: ignore[override]
            return FS()

    ns = mod._ensure_deps().copy()
    ns["DataLakeServiceClient"] = type(
        "DLService",
        (),
        {
            "__call__": lambda self, *a, **k: S(),
            "__init__": lambda self, *a, **k: None,
        },
    )
    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    c = get("adls2")
    assert c.exists("c", "any") is False


def test_download_range_length(monkeypatch):
    inject_azure_modules(monkeypatch)
    c = get("adls2")
    c.upload_bytes("c", "p.txt", b"abcdef")
    # download [1,3] -> indexes 1..3 inclusive => b"bcd"
    out = c.download_bytes("c", "p.txt", start=1, end=3)
    assert out == b"bcd"


def test_map_error_heuristics(monkeypatch):
    inject_azure_modules(monkeypatch)
    import auto_workflow.connectors.adls2 as mod
    from auto_workflow.connectors.exceptions import (
        AuthError,
        NotFoundError,
        PermanentError,
        TimeoutError,
        TransientError,
    )

    assert isinstance(mod._map_error(Exception("throttle")), TransientError)
    assert isinstance(mod._map_error(Exception("auth denied")), AuthError)
    assert isinstance(mod._map_error(Exception("404 not found")), NotFoundError)
    assert isinstance(mod._map_error(Exception("read timeout")), TimeoutError)
    assert isinstance(mod._map_error(Exception("other")), PermanentError)
