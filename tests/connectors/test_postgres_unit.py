from __future__ import annotations

import types
from contextlib import contextmanager

import pytest

from auto_workflow.connectors import get, reset
from auto_workflow.connectors.postgres import PostgresClient


class DummyConn:
    def __init__(self):
        self._tx = []
        self.row_factory = None

    def execute(self, sql):
        self._tx.append(sql)

    @contextmanager
    def cursor(self):
        yield DummyCursor()


class DummyCursor:
    rowcount = 3

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchone(self):
        return {"x": 1}

    def fetchmany(self, n):
        return [{"x": i} for i in range(n)]

    def fetchall(self):
        return [{"x": 1}, {"x": 2}]

    def executemany(self, sql, seq):
        self.sql = sql
        self.params = list(seq)


class DummyPool:
    @contextmanager
    def connection(self):
        yield DummyConn()

    def close(self):
        pass


def inject_psycopg_modules(monkeypatch):
    fake_psycopg = types.SimpleNamespace(rows=types.SimpleNamespace(dict_row=object()))
    fake_pool_mod = types.SimpleNamespace(ConnectionPool=lambda conninfo: DummyPool())
    import auto_workflow.connectors.postgres as pgmod

    monkeypatch.setitem(pgmod.__dict__, "_ensure_deps", lambda: (fake_psycopg, fake_pool_mod))


def setup_function(_):
    reset()
    # Import to trigger factory registration
    import auto_workflow.connectors.postgres  # noqa: F401


def test_query_and_execute(monkeypatch):
    inject_psycopg_modules(monkeypatch)
    c = get("postgres")
    assert isinstance(c, PostgresClient)

    rows = c.query("select 1")
    assert isinstance(rows, list)
    assert rows and "x" in rows[0]

    row = c.query("select 1", fetch="one")
    assert row["x"] == 1

    rows2 = c.query("select 1", fetch="many", size=2)
    assert len(rows2) == 2

    rc = c.execute("update t set x=1")
    assert rc == 3


def test_query_one_and_value(monkeypatch):
    inject_psycopg_modules(monkeypatch)
    c = get("postgres")
    one = c.query_one("select 1")
    assert one is not None and one.get("x") == 1
    val = c.query_value("select 1")
    assert val == 1


def test_transaction_context(monkeypatch):
    inject_psycopg_modules(monkeypatch)
    c = get("postgres")
    with c.transaction():
        # nested execute
        assert c.execute("update t set y=2") == 3


def test_error_mapping(monkeypatch):
    inject_psycopg_modules(monkeypatch)

    # Force error path by making connection() throw
    import auto_workflow.connectors.postgres as pgmod

    def boom():
        raise RuntimeError("deadlock detected")

    class BadPool(DummyPool):
        @contextmanager
        def connection(self):
            boom()
            yield  # pragma: no cover

    fake_pool_mod = types.SimpleNamespace(ConnectionPool=lambda conninfo: BadPool())
    fake_psycopg = types.SimpleNamespace(rows=types.SimpleNamespace(dict_row=object()))

    monkeypatch.setitem(pgmod.__dict__, "_ensure_deps", lambda: (fake_psycopg, fake_pool_mod))

    c = get("postgres")
    with pytest.raises(Exception) as ei:
        c.query("select 1")
    # Should be mapped (TransientError)
    assert "transient" in str(ei.value).lower()


def test_conninfo_includes_optional_fields_and_raw_pool(monkeypatch):
    inject_psycopg_modules(monkeypatch)
    # Provide full individual fields to trigger _conninfo path
    import auto_workflow.connectors.postgres as pgmod
    from auto_workflow.connectors.registry import get as reg_get, reset as reg_reset

    reg_reset()
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__HOST", "h")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__DATABASE", "d")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__USER", "u")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__PASSWORD", "p")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__SSLMODE", "require")
    monkeypatch.setenv(
        "AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__APPLICATION_NAME",
        "aw-tests",
    )

    c = reg_get("postgres")
    # Opening will construct pool using conninfo; we can't read conninfo directly,
    # but ensure raw_pool returns a pool instance and connection works
    pool = c.raw_pool()
    assert pool is not None
    with c.connection() as conn:
        assert conn is not None
