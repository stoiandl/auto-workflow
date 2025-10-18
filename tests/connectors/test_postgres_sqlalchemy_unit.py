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


def test_sqlalchemy_engine_url_variants(monkeypatch):
    inject_psycopg_modules(monkeypatch)
    seen = {}

    class DummyEngine:
        def __init__(self, url, connect_args=None, **kwargs):
            seen.setdefault("urls", []).append(url)
            seen.setdefault("connect_args", []).append(connect_args or {})

    fake_sa = types.SimpleNamespace(create_engine=lambda url, **kw: DummyEngine(url, **kw))

    def fake_sessionmaker(bind=None, **kw):
        class S:
            def __call__(self):
                return self

        return S()

    monkeypatch.setitem(pgmod.__dict__, "_ensure_sqlalchemy", lambda: (fake_sa, fake_sessionmaker))

    # Case 1: DSN with postgresql:// should be upgraded to +psycopg
    reset()
    monkeypatch.setenv(
        "AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__JSON",
        '{"dsn": "postgresql://u:p@h:5432/d"}',
    )
    c1 = get("postgres")
    _ = c1.sqlalchemy_engine()
    assert seen["urls"][-1].startswith("postgresql+psycopg://")
    assert seen["connect_args"][-1] == {}

    # Case 2: DSN as conninfo (not URL) falls back to individual fields
    reset()
    monkeypatch.delenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__JSON", raising=False)
    # Provide a conninfo-like DSN but also set fields used to build URL
    monkeypatch.setenv(
        "AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__DSN",
        "host=h port=5432 dbname=d user=u",
    )
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__HOST", "h")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__DATABASE", "d")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__USER", "u")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__PASSWORD", "p")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__SSLMODE", "require")
    c2 = get("postgres")
    _ = c2.sqlalchemy_engine()
    # URL should include password, host, db, and sslmode query
    assert "postgresql+psycopg://" in seen["urls"][-1]
    assert "@h:5432/d" in seen["urls"][-1]
    assert "sslmode=require" in seen["urls"][-1]


def test_sqlalchemy_session_string_to_text_coercion(monkeypatch):
    inject_psycopg_modules(monkeypatch)
    calls = {}

    class DummyEngine:
        def __init__(self, url, **kwargs):
            pass

    class DummySA:
        @staticmethod
        def create_engine(url, **kw):
            return DummyEngine(url, **kw)

        @staticmethod
        def text(sql):
            calls["text_called_with"] = sql
            return {"text": sql}

    def fake_sessionmaker(bind=None, **kw):
        calls["session_kwargs"] = kw

        class S:
            def __call__(self):
                return self

            def execute(self, stmt, *a, **k):
                calls["execute_arg_type"] = type(stmt)
                calls["execute_arg_val"] = stmt

            def commit(self):
                calls["committed"] = True

            def close(self):
                calls["closed"] = True

        return S()

    monkeypatch.setitem(pgmod.__dict__, "_ensure_sqlalchemy", lambda: (DummySA, fake_sessionmaker))

    c = get("postgres")
    with c.sqlalchemy_session() as s:
        # Pass a string; should be coerced via sqlalchemy.text
        s.execute("select 1")
    assert calls.get("text_called_with") == "select 1"
    assert calls.get("committed") and calls.get("closed")


def test_sqlalchemy_engine_non_default_not_cached(monkeypatch):
    inject_psycopg_modules(monkeypatch)
    instances = []

    class DummyEngine:
        def __init__(self, url, **kwargs):
            self.url = url
            self.kwargs = kwargs
            instances.append(self)

    fake_sa = types.SimpleNamespace(create_engine=lambda url, **kw: DummyEngine(url, **kw))

    def fake_sessionmaker(bind=None, **kw):
        class S:
            def __call__(self):
                return self

        return S()

    monkeypatch.setitem(pgmod.__dict__, "_ensure_sqlalchemy", lambda: (fake_sa, fake_sessionmaker))

    c = get("postgres")
    e_default = c.sqlalchemy_engine()
    e_non_default1 = c.sqlalchemy_engine(echo=True)
    e_non_default2 = c.sqlalchemy_engine(echo=True)
    # Default engine is cached (same instance), non-default is not
    assert e_default is c.sqlalchemy_engine()
    assert e_non_default1 is not e_default
    assert e_non_default2 is not e_non_default1
