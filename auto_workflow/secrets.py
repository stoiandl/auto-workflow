"""Secrets provider abstraction."""
from __future__ import annotations
from typing import Protocol, Optional, Dict
import os

class SecretsProvider(Protocol):  # pragma: no cover - interface
    def get(self, key: str) -> Optional[str]: ...

class EnvSecrets(SecretsProvider):
    def get(self, key: str) -> Optional[str]:
        return os.environ.get(key)

class StaticMappingSecrets(SecretsProvider):
    def __init__(self, data: Dict[str,str]):
        self.data = data
    def get(self, key: str) -> Optional[str]:
        return self.data.get(key)

class DummyVaultSecrets(SecretsProvider):  # placeholder for future HashiCorp Vault integration
    def __init__(self, prefix: str = ""):
        self.prefix = prefix
        # In a real implementation, store client/session
    def get(self, key: str) -> Optional[str]:  # pragma: no cover - placeholder
        # Would query Vault; here just environment fallback with prefix
        return os.environ.get(self.prefix + key)

_provider: SecretsProvider = EnvSecrets()

def set_secrets_provider(p: SecretsProvider) -> None:
    global _provider
    _provider = p

def secret(key: str) -> Optional[str]:
    return _provider.get(key)
