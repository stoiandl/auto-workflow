"""Configuration loading from pyproject.toml (best-effort)."""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "log_level": "INFO",
    "max_dynamic_tasks": 2048,
    "artifact_store": "memory",
    "artifact_store_path": ".aw_artifacts",
    "artifact_serializer": "pickle",  # or "json"
    "result_cache": "memory",
    "result_cache_path": ".aw_cache",
    "result_cache_max_entries": None,  # int or None
    "process_pool_max_workers": None,  # int or None
}


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    root = Path(__file__).resolve().parent.parent
    pyproject = root / "pyproject.toml"
    data: dict[str, Any] = {}
    if pyproject.exists():
        try:
            with pyproject.open("rb") as f:
                parsed = tomllib.load(f)
            tool_cfg = parsed.get("tool", {}).get("auto_workflow", {})
            if isinstance(tool_cfg, dict):
                data.update(tool_cfg)
        except Exception:  # pragma: no cover
            pass
    merged = {**DEFAULTS, **data}
    # env overrides
    import os

    for k in list(merged.keys()):
        env_key = f"AUTO_WORKFLOW_{k.upper()}"
        if env_key in os.environ:
            merged[k] = os.environ[env_key]

    # normalize types for known keys
    def _to_int(val):
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            try:
                return int(val)
            except Exception:
                return None
        return None

    # coerce integers
    for key in ("max_dynamic_tasks", "process_pool_max_workers", "result_cache_max_entries"):
        v = merged.get(key)
        # Preserve strings from env; Flow or call sites will coerce/ignore as needed
        if isinstance(v, str):
            continue
        iv = _to_int(v)
        if iv is not None and iv > 0:
            merged[key] = iv
        elif v is not None:
            merged[key] = None
    # constrain artifact_serializer
    if merged.get("artifact_serializer") not in ("pickle", "json"):
        merged["artifact_serializer"] = "pickle"
    return merged


def reload_config() -> dict[str, Any]:  # pragma: no cover - used in tests
    load_config.cache_clear()  # type: ignore
    return load_config()
