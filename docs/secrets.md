# Secrets Management

Secrets retrieval is abstracted behind a provider interface. Default provider reads from environment variables.

## Providers
- `EnvSecrets` (default)
- `StaticMappingSecrets` (inject dict for tests)
- `DummyVaultSecrets` (placeholder emulating a prefix-based lookup)

## Usage
```python
from auto_workflow.secrets import secret, set_secrets_provider, StaticMappingSecrets

set_secrets_provider(StaticMappingSecrets({"API_KEY": "test123"}))
print(secret("API_KEY"))  # => test123
```

## Custom Provider
Implement `get(key) -> Optional[str]`:
```python
class MyProvider:
    def get(self, key: str):
        return lookup_somewhere(key)

set_secrets_provider(MyProvider())
```

## Best Practices
- Avoid embedding secrets into task code; resolve at runtime.
- Combine with artifact persistence for decrypted payloads if needed.
