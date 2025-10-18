from __future__ import annotations

import types
from contextlib import contextmanager

import pytest

import auto_workflow.connectors.postgres as pgmod
from auto_workflow.connectors import get, reset


class DummyConn:
    def execute(self, *a, **k):
        pass


class DummyCursor:
    pass


class DummyPool:
    @contextmanager
    def connection(self):
        yield DummyConn()

    def close(self):
        pass


def inject_psycopg_modules(monkeypatch):
    fake_psycopg = types.SimpleNamespace(rows=types.SimpleNamespace(dict_row=object()))
    fake_pool_mod = types.SimpleNamespace(ConnectionPool=lambda conninfo: DummyPool())
    monkeypatch.setitem(pgmod.__dict__, "_ensure_deps", lambda: (fake_psycopg, fake_pool_mod))


def inject_sqlalchemy_modules(monkeypatch, collector: dict):
    class DummyEngine:
        def __init__(self, url, connect_args=None, **kwargs):
            collector["engine_url"] = url
            collector["connect_args"] = connect_args or {}
            collector["engine_kwargs"] = kwargs

        def dispose(self):
            collector["disposed"] = True

    class DummyMeta:
        def __init__(self):
            self._reflected = False

        def reflect(self, bind=None, schema=None, only=None):
            collector["reflected"] = {"schema": schema, "only": only, "bind": bind}
            self._reflected = True

    fake_sa = types.SimpleNamespace(
        create_engine=lambda url, **kw: DummyEngine(url, **kw),
        MetaData=lambda: DummyMeta(),
    )

    def fake_sessionmaker(bind=None, **kw):
        collector["session_bind"] = bind
        collector["session_kwargs"] = kw

        class S:
            def __call__(self):
                return self

            def commit(self):
                collector["committed"] = True

            def close(self):
                collector["closed"] = True

        return S()

    monkeypatch.setitem(pgmod.__dict__, "_ensure_sqlalchemy", lambda: (fake_sa, fake_sessionmaker))


def setup_function(_):
    reset()
    # Ensure module import for potential re-registration
    import auto_workflow.connectors.postgres  # noqa: F401


def test_sqlalchemy_engine_and_session(monkeypatch):
    inject_psycopg_modules(monkeypatch)
    collector = {}
    inject_sqlalchemy_modules(monkeypatch, collector)

    c = get("postgres")
    e1 = c.sqlalchemy_engine()
    assert "postgresql+psycopg://" in collector["engine_url"]
    sm1 = c.sqlalchemy_sessionmaker()
    # sessionmaker returns a callable S()
    sess_cm = c.sqlalchemy_session()
    with sess_cm as s:
        assert s is not None
    assert collector.get("closed") is True

    # Caching assertions (default engine/sessionmaker should be reused)
    e2 = c.sqlalchemy_engine()
    assert e1 is e2
    sm2 = c.sqlalchemy_sessionmaker()
    assert type(sm1) is type(sm2)

    # Close should dispose engine
    c.close()
    assert collector.get("disposed") is True


def test_sqlalchemy_reflect(monkeypatch):
    inject_psycopg_modules(monkeypatch)
    collector = {}
    inject_sqlalchemy_modules(monkeypatch, collector)

    c = get("postgres")
    _ = c.sqlalchemy_reflect(schema="public", only=["users"])
    assert collector["reflected"]["schema"] == "public"
    assert collector["reflected"]["only"] == ["users"]
