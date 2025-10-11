"""Example: Secrets + Artifact persistence.

Demonstrates:
- secrets provider usage
- persisting large result as artifact
"""

from __future__ import annotations

from auto_workflow import flow, task
from auto_workflow.artifacts import get_store
from auto_workflow.secrets import StaticMappingSecrets, secret, set_secrets_provider


@task
def read_api_key():
    return secret("API_KEY")


@task(persist=True)
def build_large_payload():
    return {"items": list(range(100)), "meta": {"source": "generator"}}


@flow
def secrets_artifacts_flow():
    key = read_api_key()
    payload_ref = build_large_payload()
    return {"key": key, "payload_ref": payload_ref}


if __name__ == "__main__":
    # Provide a mapping secrets provider for demonstration
    set_secrets_provider(StaticMappingSecrets({"API_KEY": "demo-key-123"}))
    out = secrets_artifacts_flow.run()
    store = get_store()
    resolved = store.get(out["payload_ref"])
    print("API key:", out["key"])
    print("Artifact keys:", list(resolved.keys()))
