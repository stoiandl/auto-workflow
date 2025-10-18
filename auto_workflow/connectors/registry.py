"""Connector registry and profile-based client factories (scaffolding).

This module avoids importing heavy SDKs. Providers register a factory callable
under a well-known name (e.g., "postgres"). Users obtain clients via `get`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import suppress
from dataclasses import asdict, is_dataclass
from typing import Any

from ..config import load_config
from .base import Connector
from .exceptions import ConfigError
from .utils import apply_env_overrides

Factory = Callable[[str, dict[str, Any]], Connector]

_REGISTRY: dict[str, Factory] = {}
# Cache by (name, profile, config_hash) to avoid recreating identical clients
_CACHE: dict[tuple[str, str, str], Connector] = {}


def register(name: str, factory: Factory) -> None:
    _REGISTRY[name] = factory


def reset() -> None:
    _REGISTRY.clear()
    _CACHE.clear()


def _normalize_config_value(val: Any) -> Any:
    if is_dataclass(val):
        try:
            return asdict(val)
        except Exception:
            pass
    if hasattr(val, "__dict__"):
        return {k: _normalize_config_value(v) for k, v in val.__dict__.items()}
    if isinstance(val, dict):
        return {k: _normalize_config_value(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_normalize_config_value(x) for x in val]
    return val


def _config_for(name: str, profile: str) -> dict[str, Any]:
    cfg = load_config()
    section = cfg.get("connectors", {})
    provider_cfg = section.get(name, {}) if isinstance(section, dict) else {}
    profile_cfg = provider_cfg.get(profile, {}) if isinstance(provider_cfg, dict) else {}
    if not isinstance(profile_cfg, dict):
        profile_cfg = {}
    # Apply env overlays
    merged = apply_env_overrides(name, profile, profile_cfg)
    return merged


def get(name: str, profile: str = "default") -> Connector:
    if name not in _REGISTRY:
        raise ConfigError(f"connector '{name}' is not registered")
    base = _config_for(name, profile)
    # Hash config for cache key (stable json)
    norm = _normalize_config_value(base)
    key = json.dumps(norm, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    cache_key = (name, profile, digest)
    if cache_key in _CACHE:
        conn = _CACHE[cache_key]
        if not conn.is_closed():
            return conn
        # Closed -> drop from cache and recreate
        _CACHE.pop(cache_key, None)
    factory = _REGISTRY[name]
    conn = factory(profile, base)
    # Ensure connector is open before returning (idempotent for lazy providers)
    with suppress(Exception):
        conn.open()
    _CACHE[cache_key] = conn
    return conn
