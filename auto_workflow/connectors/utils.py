"""Utilities shared by connector implementations (scaffolding).

Delegates environment override parsing to `auto_workflow.env_overrides`.
"""

from __future__ import annotations

from typing import Any

from ..env_overrides import apply_env_overrides as _apply_env_overrides, maybe_secret

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


def apply_env_overrides(name: str, profile: str, base: dict[str, Any]) -> dict[str, Any]:
    """Connector-flavored env overlay wrapper using shared utilities.

    Applies overrides under prefix `AUTO_WORKFLOW_CONNECTORS_<NAME>_<PROFILE>__` and
    treats `<prefix>JSON` as high precedence overlay. Secrets are resolved for known
    secret-looking keys and `secret://` values.
    """
    prefix = f"AUTO_WORKFLOW_CONNECTORS_{name.upper()}_{profile.upper()}__"
    return _apply_env_overrides(
        prefix,
        base,
        json_key="JSON",
        resolve_secrets=True,
        secret_keys=SECRET_KEYS,
    )


## Legacy helpers kept for connector-local use
def _resolve_secrets_inplace(obj: dict[str, Any]) -> None:
    for k, v in list(obj.items()):
        if isinstance(v, dict):
            _resolve_secrets_inplace(v)
        elif isinstance(v, str) and (k.lower() in SECRET_KEYS or v.startswith("secret://")):
            obj[k] = maybe_secret(v)
