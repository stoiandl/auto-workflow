"""Secrets provider abstraction."""

from __future__ import annotations

import os
from typing import Protocol


class SecretsProvider(Protocol):  # pragma: no cover - interface
    def get(self, key: str) -> str | None: ...


class EnvSecrets(SecretsProvider):
    def get(self, key: str) -> str | None:
        return os.environ.get(key)


class StaticMappingSecrets(SecretsProvider):
    def __init__(self, data: dict[str, str]):
        self.data = data

    def get(self, key: str) -> str | None:
        return self.data.get(key)


class DummyVaultSecrets(SecretsProvider):  # placeholder for future HashiCorp Vault integration
    def __init__(self, prefix: str = ""):
        self.prefix = prefix
        # In a real implementation, store client/session

    def get(self, key: str) -> str | None:  # pragma: no cover - placeholder
        # Would query Vault; here just environment fallback with prefix
        return os.environ.get(self.prefix + key)


_provider: SecretsProvider = EnvSecrets()


def set_secrets_provider(p: SecretsProvider) -> None:
    global _provider
    _provider = p


def secret(key: str) -> str | None:
    return _provider.get(key)
