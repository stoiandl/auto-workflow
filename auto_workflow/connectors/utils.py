"""Utilities shared by connector implementations (scaffolding)."""

from __future__ import annotations

import json
import os
from typing import Any

from ..secrets import secret as resolve_secret

SECRET_KEYS = {"password", "credential", "secret", "secret_access_key", "session_token"}


def redact(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        if value.startswith("secret://"):
            return "***"
        if len(value) > 8:
            return value[:4] + "***" + value[-2:]
        return "***"
    return "***"


def coerce_duration(value: str) -> float:
    # Supports 100ms, 2s, 5m
    v = value.strip().lower()
    if v.endswith("ms"):
        return float(v[:-2]) / 1000.0
    if v.endswith("s"):
        return float(v[:-1])
    if v.endswith("m"):
        return float(v[:-1]) * 60.0
    # fallback: seconds
    return float(v)


def maybe_secret(value: str | None) -> str | None:
    if value and value.startswith("secret://"):
        # Strip scheme and delegate to secrets provider (env key or logical key)
        key = value[len("secret://") :]
        return resolve_secret(key) or None
    return value


def apply_env_overrides(name: str, profile: str, base: dict[str, Any]) -> dict[str, Any]:
    """Overlay env variables using the documented scheme.

    AUTO_WORKFLOW_CONNECTORS_<NAME>_<PROFILE>__JSON has highest precedence.
    Otherwise, apply nested KEYs separated by double underscore.
    """

    prefix = f"AUTO_WORKFLOW_CONNECTORS_{name.upper()}_{profile.upper()}__"
    json_key = prefix + "JSON"
    out = dict(base)

    # Individual keys first (lower precedence)
    for k, v in os.environ.items():
        if not k.startswith(prefix):
            continue
        if k == json_key:
            continue
        path = k[len(prefix) :].split("__")
        _assign_path(out, path, _coerce(v))

    # JSON overlay last (highest precedence)
    if json_key in os.environ:
        try:
            payload = json.loads(os.environ[json_key])
            if isinstance(payload, dict):
                out = _deep_merge(out, payload)
        except Exception:
            # Ignore malformed JSON (safe default)
            pass
    # Resolve secrets markers on known fields
    _resolve_secrets_inplace(out)
    return out


def _coerce(v: str) -> Any:
    s = v.strip()
    # bool
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    # int
    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        try:
            return int(s)
        except Exception:
            pass
    # float
    try:
        return float(s)
    except Exception:
        pass
    # durations
    if any(s.endswith(u) for u in ("ms", "s", "m")):
        try:
            return coerce_duration(s)
        except Exception:
            return s
    return s


def _assign_path(obj: dict[str, Any], path: list[str], value: Any) -> None:
    cur = obj
    for key in path[:-1]:
        cur = cur.setdefault(_norm_key(key), {})
    cur[_norm_key(path[-1])] = value


def _norm_key(k: str) -> str:
    return k.lower()


def _deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    out = dict(dst)
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _resolve_secrets_inplace(obj: dict[str, Any]) -> None:
    for k, v in list(obj.items()):
        if isinstance(v, dict):
            _resolve_secrets_inplace(v)
        elif isinstance(v, str) and (k.lower() in SECRET_KEYS or v.startswith("secret://")):
            obj[k] = maybe_secret(v)
