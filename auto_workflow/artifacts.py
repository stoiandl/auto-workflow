"""Artifact storage abstraction (MVP in-memory).

Note: Pickle is only safe in trusted environments. A JSON serializer option is
available via config `artifact_serializer=json` for JSON-serializable values.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import load_config


@dataclass(slots=True)
class ArtifactRef:
    key: str


class InMemoryArtifactStore:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def put(self, value: Any) -> ArtifactRef:
        key = str(uuid.uuid4())
        self._store[key] = value
        return ArtifactRef(key)

    def get(self, ref: ArtifactRef) -> Any:
        return self._store[ref.key]


_STORE = InMemoryArtifactStore()


def get_store() -> InMemoryArtifactStore:
    cfg = load_config()
    backend = cfg.get("artifact_store", "memory")
    if backend == "memory":
        return _STORE  # type: ignore
    if backend == "filesystem":
        root = Path(cfg.get("artifact_store_path", ".aw_artifacts"))
        root.mkdir(parents=True, exist_ok=True)
        return FileSystemArtifactStore(root)  # type: ignore
    return _STORE  # fallback


class FileSystemArtifactStore:  # independent backend; no memory retention
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        # serializer: "pickle" (default) or "json" for JSON-serializable values
        self.serializer = load_config().get("artifact_serializer", "pickle")

    def _path(self, key: str) -> Path:
        return self.root / key

    def put(self, value: Any) -> ArtifactRef:
        key = str(uuid.uuid4())
        path = self._path(key)
        with path.open("wb") as f:
            # best-effort file lock (POSIX); on macOS this is fine, Windows would need msvcrt
            try:
                import fcntl

                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            except Exception:
                pass
            if self.serializer == "json":
                import json

                data = json.dumps(value).encode()
                f.write(data)
            else:
                import pickle

                pickle.dump(value, f)
            try:
                import fcntl

                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
        return ArtifactRef(key)

    def get(self, ref: ArtifactRef) -> Any:
        path = self._path(ref.key)
        if not path.exists():
            raise KeyError(f"Artifact not found: {ref.key}")
        with path.open("rb") as f:
            try:
                import fcntl

                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            except Exception:
                pass
            if self.serializer == "json":
                import json

                data = f.read()
                try:
                    import fcntl

                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                return json.loads(data.decode())
            else:
                import pickle

                try:
                    obj = pickle.load(f)
                finally:
                    try:
                        import fcntl

                        fcntl.flock(f.fileno(), fcntl.LockFlags.LOCK_UN)  # type: ignore[attr-defined]
                    except Exception:
                        # Fallback for Python versions without LockFlags
                        try:
                            import fcntl as _fcntl

                            _fcntl.flock(f.fileno(), _fcntl.LOCK_UN)
                        except Exception:
                            pass
                return obj
