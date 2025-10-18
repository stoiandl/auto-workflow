from __future__ import annotations


def test_import_connectors_smoke():
    # Should import without raising even if heavy deps aren't installed
    import auto_workflow.connectors  # noqa: F401
    import auto_workflow.connectors.postgres as pg  # noqa: F401

    # Registry get should work without opening a real connection (open is lazy and tolerated)
    from auto_workflow.connectors import get, reset

    reset()
    _ = get("postgres")
