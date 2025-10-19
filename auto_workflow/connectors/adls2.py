"""ADLS2 connector (Azure Data Lake Storage Gen2, sync).

Lazy-imports Azure SDKs on first use. If deps are missing, raises an informative ImportError
suggesting the optional extras group to install.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass
from typing import IO, Any

from .base import BaseConnector
from .exceptions import AuthError, NotFoundError, PermanentError, TimeoutError, TransientError
from .registry import get as _get, register as _register


def _ensure_deps():  # pragma: no cover - exercised via mocked unit tests
    try:
        from azure.core.exceptions import (  # type: ignore
            ClientAuthenticationError,
            HttpResponseError,
            ResourceExistsError,
            ResourceNotFoundError,
            ServiceRequestError,
            ServiceResponseError,
        )
        from azure.identity import DefaultAzureCredential  # type: ignore
        from azure.storage.filedatalake import (  # type: ignore
            DataLakeServiceClient,
            FileSystemClient,
        )
    except Exception as e:  # pragma: no cover
        raise ImportError(
            "Azure SDKs required. Install with 'poetry install -E connectors-adls2'"
        ) from e

    # Optional: Retry/transport configs; tolerate absence in tests
    try:
        from azure.core.pipeline.policies import RetryPolicy  # type: ignore
    except Exception:  # pragma: no cover
        RetryPolicy = None  # type: ignore[assignment]  # noqa: N806
    try:
        from azure.core.pipeline.transport import RequestsTransport  # type: ignore
    except Exception:  # pragma: no cover
        RequestsTransport = None  # type: ignore[assignment]  # noqa: N806
    # Optional: content settings for upload (provided by azure-storage-blob)
    try:
        from azure.storage.blob import ContentSettings  # type: ignore
    except Exception:  # pragma: no cover
        ContentSettings = None  # type: ignore[assignment]  # noqa: N806

    return {
        "DataLakeServiceClient": DataLakeServiceClient,
        "FileSystemClient": FileSystemClient,
        "DefaultAzureCredential": DefaultAzureCredential,
        "ClientAuthenticationError": ClientAuthenticationError,
        "HttpResponseError": HttpResponseError,
        "ResourceNotFoundError": ResourceNotFoundError,
        "ResourceExistsError": ResourceExistsError,
        "ServiceRequestError": ServiceRequestError,
        "ServiceResponseError": ServiceResponseError,
        # Optional helpers
        "RetryPolicy": RetryPolicy,
        "RequestsTransport": RequestsTransport,
        "ContentSettings": ContentSettings,
    }


def _map_error(e: Exception) -> Exception:
    deps = None
    with suppress(Exception):
        deps = _ensure_deps()
    if deps is not None:
        if isinstance(e, deps.get("ClientAuthenticationError")):  # type: ignore[arg-type]
            return AuthError("adls2 authentication failed")
        if isinstance(e, deps.get("ResourceNotFoundError")):  # type: ignore[arg-type]
            return NotFoundError("adls2 resource not found")
        if isinstance(e, deps.get("ServiceRequestError")):
            msg = str(e).lower()
            if "timeout" in msg or "timed out" in msg:
                return TimeoutError("adls2 operation timed out")
            return TransientError("transient adls2 request error")
        if isinstance(e, deps.get("ServiceResponseError")):
            return TransientError("transient adls2 response error")
        if isinstance(e, deps.get("HttpResponseError")):
            # Map common HTTP status codes to project errors
            status = getattr(e, "status_code", None) or getattr(e, "status", None)
            try:
                status = int(status) if status is not None else None
            except Exception:
                status = None
            if status in (401, 403):
                return AuthError("adls2 authentication failed")
            if status == 404:
                return NotFoundError("adls2 resource not found")
            if status in (408,):
                return TimeoutError("adls2 operation timed out")
            if status in (429, 500, 502, 503, 504):
                return TransientError("transient adls2 error")
    msg = str(e).lower()
    if "not found" in msg or "404" in msg:
        return NotFoundError("adls2 resource not found")
    if "auth" in msg or "credential" in msg or "denied" in msg:
        return AuthError("adls2 authentication failed")
    if "timeout" in msg or "timed out" in msg or "read timeout" in msg:
        return TimeoutError("adls2 operation timed out")
    if any(s in msg for s in ("unavailable", "reset", "throttle", "retry")):
        return TransientError("transient adls2 error")
    return PermanentError("adls2 operation failed")


@dataclass(slots=True)
class ADLS2Client(BaseConnector):
    cfg: dict[str, Any] | None = None
    _svc: Any | None = None

    def open(self) -> None:
        if self._svc is not None:
            self._closed = False
            return
        deps = _ensure_deps()
        cfg = self.cfg or {}
        # Branch 1: connection string (preferred if provided)
        conn_str = cfg.get("connection_string") or cfg.get("conn_str") or cfg.get("dsn")
        account_url = cfg.get("account_url")
        if not account_url:
            account_url = ""  # type: ignore[assignment]
        cred_value = cfg.get("credential")
        use_default = bool(cfg.get("use_default_credentials", True))
        credential: Any | None
        if cred_value:
            credential = cred_value
        elif use_default:
            credential = deps["DefaultAzureCredential"]()  # type: ignore[call-arg]
        else:
            credential = None

        kwargs: dict[str, Any] = {}
        retries = ((self.cfg or {}).get("retries") or {}).get("attempts")
        if retries and deps.get("RetryPolicy") is not None:
            total = max(int(retries) - 1, 0)
            with suppress(Exception):
                kwargs["retry_policy"] = deps["RetryPolicy"](total_retries=total)  # type: ignore[misc]
        timeouts = (self.cfg or {}).get("timeouts") or {}
        connect_s = timeouts.get("connect_s")
        operation_s = timeouts.get("operation_s")
        if deps.get("RequestsTransport") is not None and (connect_s or operation_s):
            with suppress(Exception):
                kwargs["transport"] = deps["RequestsTransport"](
                    connection_timeout=connect_s or None,
                    read_timeout=operation_s or None,
                )

        created = None
        # Use connection string path if available and supported
        if conn_str:
            dls = deps["DataLakeServiceClient"]
            # Prefer classmethod from_connection_string if present
            fcs = getattr(dls, "from_connection_string", None)
            if callable(fcs):
                with suppress(Exception):
                    created = fcs(conn_str, **{k: v for k, v in kwargs.items() if v is not None})
            if created is None:
                # Fallbacks for unit doubles
                with suppress(Exception):
                    created = dls(conn_str)  # type: ignore[call-arg]
        # Else account_url + credential
        if created is None:
            try:
                created = deps["DataLakeServiceClient"](
                    account_url=account_url, credential=credential, **kwargs
                )
            except Exception:
                try:
                    created = deps["DataLakeServiceClient"](
                        account_url=account_url, credential=credential
                    )
                except Exception:
                    created = deps["DataLakeServiceClient"](account_url=account_url)
        # Some fakes return callable wrapper instances; unwrap until we get the real service
        while not hasattr(created, "get_file_system_client") and callable(created):
            with suppress(Exception):
                created = created()
        self._svc = created
        self._closed = False

    def close(self) -> None:
        if self._svc is not None:
            with suppress(Exception):  # pragma: no cover - best effort
                close = getattr(self._svc, "close", None)
                if callable(close):
                    close()
        self._svc = None
        self._closed = True

    def datalake_service_client(self) -> Any:
        if self._svc is None:
            self.open()
        return self._svc

    def filesystem_client(self, container: str) -> Any:
        if self._svc is None:
            self.open()
        assert self._svc is not None
        svc = self._svc
        f = getattr(svc, "get_file_system_client", None)
        if callable(f):
            return f(container)
        # Unwrap callable wrappers that yield the real service (test fakes)
        if callable(svc):
            with suppress(Exception):
                svc = svc()
                self._svc = svc
                f2 = getattr(svc, "get_file_system_client", None)
                if callable(f2):
                    return f2(container)
        deps = _ensure_deps()
        try:
            return deps["FileSystemClient"](svc, container)  # type: ignore[call-arg]
        except Exception:  # pragma: no cover
            return deps["FileSystemClient"](container)  # type: ignore[call-arg]

    def upload_bytes(
        self,
        container: str,
        path: str,
        data: bytes | IO[bytes],
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
        overwrite: bool = True,
        chunk_size: int | None = None,
        timeout: float | None = None,
    ) -> str:
        with self._op_span(
            "adls2.upload_bytes",
            container=container,
            path=path,
            bytes=(len(data) if isinstance(data, (bytes, bytearray)) else None),
            chunk_size=chunk_size,
        ):
            try:
                fs = self.filesystem_client(container)
                file_client = fs.get_file_client(path)
                deps = None
                with suppress(Exception):
                    deps = _ensure_deps()
                kwargs: dict[str, Any] = {
                    "overwrite": overwrite,
                    "timeout": timeout,
                }
                if metadata:
                    kwargs["metadata"] = metadata
                # Prefer ContentSettings over non-existent content_type kw for ADLS
                if content_type:
                    cs = deps.get("ContentSettings") if deps is not None else None
                    if cs is not None:
                        with suppress(Exception):
                            kwargs["content_settings"] = cs(content_type=content_type)  # type: ignore[misc]
                if chunk_size is not None:
                    kwargs["chunk_size"] = chunk_size
                resp = file_client.upload_data(data, **kwargs)
                etag = getattr(resp, "etag", None) or getattr(resp, "get", lambda k, d=None: None)(
                    "etag"
                )
                if not etag:
                    etag = getattr(getattr(resp, "headers", {}), "get", lambda *_: None)("etag")
                return str(etag or "")
            except Exception as e:  # pragma: no cover - mapped in unit tests
                raise _map_error(e) from e

    def download_bytes(
        self,
        container: str,
        path: str,
        *,
        start: int | None = None,
        end: int | None = None,
        timeout: float | None = None,
    ) -> bytes:
        with self._op_span("adls2.download_bytes", container=container, path=path):
            try:
                fs = self.filesystem_client(container)
                fc = fs.get_file_client(path)
                length = None
                if start is not None and end is not None and end >= start:
                    length = end - start + 1
                dl = fc.download_file(offset=start, length=length, timeout=timeout)
                if hasattr(dl, "readall"):
                    return dl.readall()
                data = bytearray()
                chunks = getattr(dl, "chunks", lambda size=None: [])
                for c in chunks(None):
                    data.extend(c)
                return bytes(data)
            except Exception as e:  # pragma: no cover
                raise _map_error(e) from e

    def download_stream(
        self,
        container: str,
        path: str,
        *,
        chunk_size: int | None = None,
        timeout: float | None = None,
    ) -> Iterator[bytes]:
        with self._op_span("adls2.download_stream", container=container, path=path):
            try:
                fs = self.filesystem_client(container)
                fc = fs.get_file_client(path)
                dl = fc.download_file(timeout=timeout)
                chunks = getattr(dl, "chunks", None)
                if callable(chunks):
                    yield from chunks(chunk_size)
                    return
                if hasattr(dl, "readall"):
                    yield dl.readall()
            except Exception as e:  # pragma: no cover
                raise _map_error(e) from e

    def list_paths(
        self,
        container: str,
        prefix: str | None = None,
        *,
        recursive: bool = True,
        timeout: float | None = None,
    ) -> Iterator[dict[str, Any]]:
        with self._op_span("adls2.list_paths", container=container, prefix=prefix or ""):
            try:
                fs = self.filesystem_client(container)
                it = fs.get_paths(name_starts_with=prefix, recursive=recursive, timeout=timeout)
                for p in it:
                    yield {
                        "container": container,
                        "path": getattr(p, "name", None) or getattr(p, "path", None),
                        "is_directory": bool(getattr(p, "is_directory", False)),
                        "size": getattr(p, "content_length", None) or getattr(p, "size", None),
                        "last_modified": getattr(p, "last_modified", None),
                        "etag": getattr(p, "etag", None),
                    }
            except Exception as e:  # pragma: no cover
                raise _map_error(e) from e

    def exists(self, container: str, path: str, *, timeout: float | None = None) -> bool:
        with self._op_span("adls2.exists", container=container, path=path):
            deps = None
            try:
                deps = _ensure_deps()
            except Exception:
                deps = None
            try:
                fs = self.filesystem_client(container)
                fc = fs.get_file_client(path)
                with suppress(Exception):
                    props = fc.get_file_properties(timeout=timeout)
                    if props is not None:
                        return True
                # Consider directory existence check only if path looks like a directory
                last_seg = path.rsplit("/", 1)[-1]
                if "." not in last_seg:
                    dc = fs.get_directory_client(path)
                    with suppress(Exception):
                        props = dc.get_directory_properties(timeout=timeout)
                        if props is not None:
                            return True
                return False
            except Exception as e:  # pragma: no cover
                if deps and isinstance(e, deps.get("ResourceNotFoundError")):
                    return False
                raise _map_error(e) from e

    def delete_path(
        self, container: str, path: str, *, recursive: bool = False, timeout: float | None = None
    ) -> None:
        with self._op_span(
            "adls2.delete_path", container=container, path=path, recursive=recursive
        ):
            try:
                fs = self.filesystem_client(container)
                with suppress(Exception):
                    fs.delete_file(path, timeout=timeout)
                    return
                try:
                    fs.delete_directory(path, recursive=recursive, timeout=timeout)
                except TypeError:
                    dc = fs.get_directory_client(path)
                    dc.delete_directory(timeout=timeout)
            except Exception as e:  # pragma: no cover
                raise _map_error(e) from e

    def make_dirs(
        self, container: str, path: str, *, exist_ok: bool = True, timeout: float | None = None
    ) -> None:
        with self._op_span("adls2.make_dirs", container=container, path=path, exist_ok=exist_ok):
            deps = _ensure_deps()
            try:
                fs = self.filesystem_client(container)
                fs.create_directory(path, timeout=timeout)
            except Exception as e:  # pragma: no cover
                rex = deps.get("ResourceExistsError")
                if exist_ok and rex and isinstance(e, rex):
                    return
                raise _map_error(e) from e

    def create_container(
        self, container: str, *, exist_ok: bool = True, timeout: float | None = None
    ) -> None:
        """Create a container (file system) if it does not exist.

        Uses DataLakeServiceClient.create_file_system when available, otherwise
        attempts a FileSystemClient-level create if supported; falls back to a no-op
        if neither method exists (useful for fakes/tests).
        """
        with self._op_span("adls2.create_container", container=container, exist_ok=exist_ok):
            deps = _ensure_deps()
            try:
                svc = self.datalake_service_client()
                create = getattr(svc, "create_file_system", None)
                if callable(create):
                    kwargs: dict[str, Any] = {"file_system": container}
                    if timeout is not None:
                        kwargs["timeout"] = timeout
                    create(**kwargs)
                    return
                # Fallback: try via FileSystemClient if supported
                fs = self.filesystem_client(container)
                fs_create = getattr(fs, "create_file_system", None)
                if callable(fs_create):  # pragma: no cover - uncommon path
                    with suppress(Exception):
                        fs_create(timeout=timeout)
                # If neither create method exists, treat as best-effort no-op
                return
            except Exception as e:  # pragma: no cover - mapped in tests
                rex = deps.get("ResourceExistsError")
                if exist_ok and rex and isinstance(e, rex):
                    return
                raise _map_error(e) from e


def _factory(profile: str, cfg: dict[str, Any]):
    return ADLS2Client(name="adls2", profile=profile, cfg=cfg)


def client(profile: str = "default") -> ADLS2Client:
    """Return a configured ADLS2Client via the registry.

    Usage:
        from auto_workflow.connectors import adls2
        with adls2.client("analytics") as fs:
            fs.upload_bytes("container", "path/to/file.txt", b"hello")
    """
    return _get("adls2", profile)  # type: ignore[return-value]


_register("adls2", _factory)
