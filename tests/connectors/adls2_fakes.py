from __future__ import annotations

from typing import Any

from auto_workflow.connectors import registry as _registry

# Shared fakes used across all ADLS2 tests (unit + integration)


class DummyDownloader:
    def __init__(self, data: bytes):
        self._data = data

    def readall(self):
        return self._data

    def chunks(self, size=None):  # pragma: no cover - fallback path
        yield self._data


class DummyFileClient:
    def __init__(self, storage: dict[str, bytes], path: str):
        self.storage = storage
        self.path = path

    def upload_data(self, data, **kwargs):
        if isinstance(data, (bytes, bytearray)):
            self.storage[self.path] = bytes(data)
        else:
            # file-like
            self.storage[self.path] = data.read()

        class Resp:
            etag = "dummy-etag"

        return Resp()

    def download_file(self, offset=None, length=None, timeout=None):
        b = self.storage.get(self.path, b"")
        if offset is not None and length is not None:
            b = b[offset : offset + length]
        return DummyDownloader(b)

    def get_file_properties(self, timeout=None):
        if self.path in self.storage:
            return {"ok": True}
        raise FileNotFoundError(self.path)


class DummyDirClient:
    def __init__(self, storage: dict[str, bytes], path: str):
        self.storage = storage
        self.path = path

    def get_directory_properties(self, timeout=None):  # pragma: no cover - rarely used in unit
        return {"ok": True}

    def delete_directory(self, timeout=None):  # pragma: no cover - fallback
        return None


class DummyFS:
    def __init__(self):
        self.storage: dict[str, bytes] = {}

    def get_file_client(self, path: str):
        return DummyFileClient(self.storage, path)

    def get_directory_client(self, path: str):
        return DummyDirClient(self.storage, path)

    def get_paths(self, name_starts_with=None, recursive=True, timeout=None):
        prefix = name_starts_with or ""
        for p, b in self.storage.items():
            if p.startswith(prefix):

                class P:
                    name = p
                    is_directory = False
                    content_length = len(b)
                    etag = "e1"

                yield P()

    def delete_file(self, path: str, timeout=None):
        self.storage.pop(path, None)

    def delete_directory(self, path: str, recursive=False, timeout=None):  # pragma: no cover
        # no-op for tests
        return None

    def create_directory(self, path: str, timeout=None):  # pragma: no cover
        return None


class DummySvc:
    def __init__(self):
        self.fs = {}

    def get_file_system_client(self, name: str):
        if name not in self.fs:
            self.fs[name] = DummyFS()
        return self.fs[name]

    def close(self):  # pragma: no cover - not essential
        pass


# Process-wide singleton service so tests share state
_SVC = DummySvc()


def inject(
    monkeypatch,
    *,
    with_conn_str: bool = False,
    retries: int | None = None,
    timeouts: dict[str, Any] | None = None,
) -> None:
    import auto_workflow.connectors.adls2 as mod

    class ClientAuthError(Exception):
        pass

    class NotFoundError(Exception):
        pass

    class ResourceExistsError(Exception):
        pass

    class ServiceReqError(Exception):
        pass

    class ServiceRespError(Exception):  # pragma: no cover - not used in tests
        pass

    class HttpResponseError(Exception):  # pragma: no cover - not used in tests
        def __init__(self, status_code=None):
            self.status_code = status_code

    class _RetryPolicy:
        def __init__(self, total_retries=0, *a, **k):  # pragma: no cover - no behavior
            self.total_retries = total_retries

    class _Transport:
        def __init__(self, connection_timeout=None, read_timeout=None, *a, **k):  # pragma: no cover
            self.connection_timeout = connection_timeout
            self.read_timeout = read_timeout

    class _DLService:
        def __init__(self, *a, **k):
            pass

        def __call__(self, *a, **k):
            return _SVC

        @classmethod
        def from_connection_string(cls, *a, **k):
            return _SVC

    ns = {
        "DataLakeServiceClient": _DLService,
        "FileSystemClient": DummyFS,
        "DefaultAzureCredential": lambda: object(),
        "ClientAuthenticationError": ClientAuthError,
        "ResourceNotFoundError": NotFoundError,
        "ResourceExistsError": ResourceExistsError,
        "ServiceRequestError": ServiceReqError,
        "ServiceResponseError": ServiceRespError,
        "HttpResponseError": HttpResponseError,
        "RetryPolicy": _RetryPolicy,
        "RequestsTransport": _Transport,
    }

    monkeypatch.setitem(mod.__dict__, "_ensure_deps", lambda: ns)

    if with_conn_str:
        orig = _registry._config_for

        def _fake_config_for(name: str, profile: str):  # type: ignore
            if name == "adls2":
                cfg = {"connection_string": "UseDevelopmentStorage=true;"}
                if retries is not None:
                    cfg["retries"] = {"attempts": retries}
                if timeouts is not None:
                    cfg["timeouts"] = timeouts
                return cfg
            return orig(name, profile)

        monkeypatch.setattr(_registry, "_config_for", _fake_config_for)
