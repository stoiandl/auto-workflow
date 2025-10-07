"""Configuration loading from pyproject.toml (best-effort)."""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "default_executor": "async",
    "log_level": "INFO",
    "max_dynamic_tasks": 2048,
    "artifact_store": "memory",
    "artifact_store_path": ".aw_artifacts",
    "result_cache": "memory",
    "result_cache_path": ".aw_cache",
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
    return merged


def reload_config() -> dict[str, Any]:  # pragma: no cover - used in tests
    load_config.cache_clear()  # type: ignore
    return load_config()
