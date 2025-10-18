from __future__ import annotations

from auto_workflow.connectors import utils as cu


def test_legacy_secret_resolution_inplace():
    data = {
        "password": "secret://db/pass",  # key in SECRET_KEYS
        "nested": {
            "credential": "secret://svc/cred",  # key in SECRET_KEYS
            "other": "not-a-secret",
        },
        "literal_secret": "secret://will_be_none_without_provider",
    }
    cu._resolve_secrets_inplace(data)
    # Values are resolved via maybe_secret and may become None without a provider
    assert data["password"] is None
    assert data["nested"]["credential"] is None
    # untouched
    assert data["nested"]["other"] == "not-a-secret"
    # values that look like secret schemes are also processed
    assert data["literal_secret"] is None
