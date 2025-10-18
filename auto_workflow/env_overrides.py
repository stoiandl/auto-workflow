"""Shared environment override utilities.

Provides generic helpers to overlay configuration dictionaries with environment
variables using a predictable nested key scheme and optional JSON overlay with
highest precedence. Also supports basic type coercion and secret resolution via
`auto_workflow.secrets` when values use `secret://` scheme.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from typing import Any

from .secrets import secret as resolve_secret


def coerce_duration(value: str) -> float:
    v = value.strip().lower()
    if v.endswith("ms"):
        return float(v[:-2]) / 1000.0
    if v.endswith("s"):
        return float(v[:-1])
    if v.endswith("m"):
        return float(v[:-1]) * 60.0
    return float(v)


def maybe_secret(value: str | None) -> str | None:
    if value and value.startswith("secret://"):
        key = value[len("secret://") :]
        return resolve_secret(key) or None
    return value


def apply_env_overrides(
    prefix: str,
    base: dict[str, Any],
    *,
    json_key: str = "JSON",
    resolve_secrets: bool = True,
    secret_keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Apply environment overrides to base config with a given prefix.

    Rules:
    - All env vars starting with `prefix` are considered. Nested keys are delimited
      by double underscore `__`.
    - The env var `<prefix><json_key>` (by default `<prefix>JSON`) is parsed as JSON
      and overlayed last with highest precedence.
    - Values are coerced to bool/int/float or durations (ms/s/m) when possible.
    - If `resolve_secrets` is True, values of keys in `secret_keys`, or values starting
      with `secret://`, are resolved via `auto_workflow.secrets.secret`.
    """

    out = dict(base)
    json_env = prefix + json_key

    # individual keys first (lower precedence)
    for k, v in os.environ.items():
        if not k.startswith(prefix):
            continue
        if k == json_env:
            continue
        path = k[len(prefix) :].split("__")
        _assign_path(out, path, _coerce(v))

    # JSON overlay last (highest precedence)
    if json_env in os.environ:
        try:
            payload = json.loads(os.environ[json_env])
            if isinstance(payload, dict):
                out = _deep_merge(out, payload)
        except Exception:
            # ignore malformed JSON
            pass

    if resolve_secrets:
        _resolve_secrets_inplace(out, set(secret_keys or ()))
    return out


def _coerce(v: str) -> Any:
    s = v.strip()
    ls = s.lower()
    # bool
    if ls in ("true", "false"):
        return ls == "true"
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
    if any(ls.endswith(u) for u in ("ms", "s", "m")):
        try:
            return coerce_duration(s)
        except Exception:
            return s
    return s


def _assign_path(obj: dict[str, Any], path: list[str], value: Any) -> None:
    cur = obj
    for key in path[:-1]:
        cur = cur.setdefault(key.lower(), {})
    cur[path[-1].lower()] = value


def _deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    out = dict(dst)
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _resolve_secrets_inplace(obj: dict[str, Any], secret_keys: set[str]) -> None:
    for k, v in list(obj.items()):
        if isinstance(v, dict):
            _resolve_secrets_inplace(v, secret_keys)
        elif isinstance(v, str) and (k.lower() in secret_keys or v.startswith("secret://")):
            obj[k] = maybe_secret(v)
