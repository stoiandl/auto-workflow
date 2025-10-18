from __future__ import annotations

import os
import types
from contextlib import contextmanager

import pytest

import auto_workflow.connectors.postgres as pgmod
from auto_workflow.connectors import get, reset


class TxConn:
    def __init__(self):
        self._tx: list[str] = []
        self.row_factory = None
        self.executed: list[tuple[str, tuple | dict | None]] = []

    def execute(self, sql, *_, **__):
        self._tx.append(sql)
        self.executed.append((sql, None))

    @contextmanager
    def cursor(self):
        yield TxCursor(self)


class TxCursor:
    def __init__(self, conn: TxConn):
        self.conn = conn
        self.sql = None
        self.params = None
        self.rowcount = 0

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params
        self.conn.executed.append((sql, params))

    def fetchone(self):
        return {"x": 1}

    def fetchmany(self, n):
        return [{"x": i} for i in range(n)]

    def fetchall(self):
        return [{"x": 1}, {"x": 2}]

    def executemany(self, sql, seq):
        self.sql = sql
        self.params = list(seq)
        self.rowcount = len(self.params)


class PoolCapturing:
    def __init__(self, collector: dict):
        self.collector = collector

    @contextmanager
    def connection(self):
        c = TxConn()
        # expose for assertions
        self.collector.setdefault("connections", []).append(c)
        yield c

    def close(self):
        self.collector["pool_closed"] = True


class PoolRaisingOnConnect:
    @contextmanager
    def connection(self):
        raise RuntimeError("canceling statement due to statement timeout")
        yield  # pragma: no cover


class PoolConnReset:
    @contextmanager
    def connection(self):
        raise RuntimeError("connection reset by peer")
        yield  # pragma: no cover


class ConnExecuteRaises(TxConn):
    def execute(self, sql, *_, **__):
        raise RuntimeError("no direct execute")


class PoolWithConnExecuteRaises:
    @contextmanager
    def connection(self):
        yield ConnExecuteRaises()

    def close(self):
        pass


def inject_psycopg(monkeypatch, pool):
    fake_psycopg = types.SimpleNamespace(rows=types.SimpleNamespace(dict_row=object()))
    fake_pool_mod = types.SimpleNamespace(ConnectionPool=lambda conninfo: pool)
    monkeypatch.setitem(pgmod.__dict__, "_ensure_deps", lambda: (fake_psycopg, fake_pool_mod))


@pytest.fixture(autouse=True)
def _reset_and_clean_env(monkeypatch):
    # Clean connector envs
    for k in list(os.environ.keys()):
        if k.startswith("AUTO_WORKFLOW_CONNECTORS_POSTGRES_"):
            monkeypatch.delenv(k, raising=False)
    reset()
    import auto_workflow.connectors.postgres  # noqa: F401


def test_env_overrides_and_conninfo(monkeypatch):
    collector: dict = {}
    pool = PoolCapturing(collector)
    inject_psycopg(monkeypatch, pool)
    # Set overrides; JSON should take precedence
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__HOST", "env-host")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__PORT", "5433")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__DATABASE", "mydb")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__USER", "bob")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__PASSWORD", "p@s")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__SSLMODE", "disable")
    monkeypatch.setenv(
        "AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__JSON",
        '{"host": "json-host", "sslmode": "require"}',
    )

    c = get("postgres")
    # trigger opening pool and a connection to set row_factory
    with c.connection():
        pass
    assert collector.get("connections"), "expected a connection"
    # ensure row_factory set
    conn = collector["connections"][0]
    assert conn.row_factory is not None


def test_statement_timeout_sets_local(monkeypatch):
    collector: dict = {}
    pool = PoolCapturing(collector)
    inject_psycopg(monkeypatch, pool)
    c = get("postgres")
    c.query("select 1", timeout=1.5)
    # First statement should be SET LOCAL
    assert any("statement_timeout" in s and "1500" in s for s in collector["connections"][0]._tx)


def test_statement_timeout_fallback_cursor(monkeypatch):
    pool = PoolWithConnExecuteRaises()
    inject_psycopg(monkeypatch, pool)
    c = get("postgres")
    # Should not raise when setting timeout, falls back to cursor
    c.query("select 1", timeout=2.0)


def test_error_mapping_timeout(monkeypatch):
    pool = PoolRaisingOnConnect()
    inject_psycopg(monkeypatch, pool)
    c = get("postgres")
    with pytest.raises(Exception) as ei:
        c.query("select 1")
    assert "timed out" in str(ei.value).lower()


def test_error_mapping_transient(monkeypatch):
    pool = PoolConnReset()
    inject_psycopg(monkeypatch, pool)
    c = get("postgres")
    with pytest.raises(Exception) as ei:
        c.query("select 1")
    assert "transient" in str(ei.value).lower()


def test_error_mapping_permanent(monkeypatch):
    class PoolBoom:
        @contextmanager
        def connection(self):
            raise RuntimeError("boom")
            yield  # pragma: no cover

    inject_psycopg(monkeypatch, PoolBoom())
    c = get("postgres")
    with pytest.raises(Exception) as ei:
        c.query("select 1")
    assert "failed" in str(ei.value).lower()


def test_error_mapping_auth(monkeypatch):
    class PoolBoom:
        @contextmanager
        def connection(self):
            raise RuntimeError("password authentication failed for user 'x'")
            yield  # pragma: no cover

    inject_psycopg(monkeypatch, PoolBoom())
    c = get("postgres")
    with pytest.raises(Exception) as ei:
        c.query("select 1")
    assert "authentication" in str(ei.value).lower()


def test_transaction_rollback_and_commit(monkeypatch):
    collector: dict = {}
    pool = PoolCapturing(collector)
    inject_psycopg(monkeypatch, pool)
    c = get("postgres")
    with pytest.raises(RuntimeError), c.transaction():
        # ensure statements run on same connection
        with c.connection() as conn_inside:
            conn_inside.execute("INSERT INTO t(v) VALUES (1)")
        raise RuntimeError("fail inside")
    # Expect BEGIN then ROLLBACK
    tx = collector["connections"][0]._tx
    assert tx[0].upper().startswith("BEGIN") and any("ROLLBACK" in s.upper() for s in tx)

    # Happy path commit
    collector.clear()
    pool = PoolCapturing(collector)
    inject_psycopg(monkeypatch, pool)
    c2 = get("postgres")
    with c2.transaction():
        # nested statement
        c2.execute("UPDATE t SET v=2 WHERE 1=0")
    tx2 = collector["connections"][0]._tx
    assert any("COMMIT" in s.upper() for s in tx2)


def test_transaction_binds_same_connection(monkeypatch):
    collector: dict = {}
    pool = PoolCapturing(collector)
    inject_psycopg(monkeypatch, pool)
    c = get("postgres")
    with c.transaction():
        # both execute and query should use same TxConn instance
        c.execute("UPDATE x SET v=1")
        _ = c.query("SELECT 1 AS x", fetch="one")
    conns = collector.get("connections", [])
    assert len(conns) == 1


def test_nested_transactions_do_not_double_begin(monkeypatch):
    collector: dict = {}
    pool = PoolCapturing(collector)
    inject_psycopg(monkeypatch, pool)
    c = get("postgres")
    with c.transaction(), c.transaction():
        c.execute("UPDATE t SET v=3 WHERE 1=0")
    tx = collector["connections"][0]._tx
    # Only one BEGIN at outermost
    begins = [s for s in tx if s.upper().startswith("BEGIN")]
    assert len(begins) == 1


def test_transaction_begin_options_emitted(monkeypatch):
    collector: dict = {}
    pool = PoolCapturing(collector)
    inject_psycopg(monkeypatch, pool)
    c = get("postgres")
    with c.transaction(isolation="serializable", readonly=True, deferrable=True):
        c.execute("SELECT 1")
    tx = collector["connections"][0]._tx
    assert tx, "expected tx statements"
    begin = tx[0]
    up = begin.upper()
    assert "BEGIN" in up and "ISOLATION LEVEL SERIALIZABLE" in up
    assert "READ ONLY" in up and "DEFERRABLE" in up


def test_registry_caching_and_eviction(monkeypatch):
    pool = PoolCapturing({})
    inject_psycopg(monkeypatch, pool)
    a = get("postgres")
    b = get("postgres")
    assert a is b, "expected cached connector"
    a.close()
    c = get("postgres")
    assert c is not a


def test_registry_lazy_import_without_prior_import():
    # Do not monkeypatch deps so open() may fail, but registry should still register
    reset()
    # Do not import pgmod here; get should lazy import and register without raising
    c = get("postgres")
    from auto_workflow.connectors.postgres import PostgresClient  # noqa

    assert isinstance(c, PostgresClient)


def test_sqlalchemy_missing_dep_raises(monkeypatch):
    pool = PoolCapturing({})
    inject_psycopg(monkeypatch, pool)

    def boom():
        raise ImportError("no SA")

    monkeypatch.setitem(pgmod.__dict__, "_ensure_sqlalchemy", boom)
    c = get("postgres")
    with pytest.raises(ImportError):
        c.sqlalchemy_engine()


def test_pool_open_fallbacks_cover_min_size_kwargs(monkeypatch):
    """Exercise both ConnectionPool fallback branches in open().

    First attempt passes open=True (raises TypeError), second attempt passes **pool_kwargs
    when min_size is set (also raises TypeError), third attempt succeeds with positional only.
    """
    collector: dict = {}

    class DummyPoolKWFail:
        def connection(self):
            return PoolCapturing(collector).connection()

        def close(self):
            collector["closed"] = True

    # ConnectionPool expects only positional arg; keywords cause TypeError
    # on first and second attempts.
    fake_pool_mod = types.SimpleNamespace(
        ConnectionPool=lambda conninfo, **kwargs: (_ for _ in ()).throw(TypeError("bad kw"))
    )
    # For the last attempt (positional only), we need a callable that accepts
    # only conninfo; emulate success when no kwargs are passed.
    calls = {"count": 0}

    def cp(conninfo, **kwargs):  # type: ignore[no-redef]
        calls["count"] += 1
        # First: has open=True -> TypeError; Second: has min_size -> TypeError
        if kwargs:
            raise TypeError("kwargs not supported")
        # Third: no kwargs path, succeed by returning a pool with context manager
        return PoolCapturing(collector)

    fake_pool_mod = types.SimpleNamespace(ConnectionPool=cp)
    fake_psycopg = types.SimpleNamespace(rows=types.SimpleNamespace(dict_row=object()))
    monkeypatch.setitem(pgmod.__dict__, "_ensure_deps", lambda: (fake_psycopg, fake_pool_mod))

    # Set min_size so **pool_kwargs is non-empty and second attempt raises
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__HOST", "h")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__DATABASE", "d")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__USER", "u")
    monkeypatch.setenv("AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__MIN_SIZE", "1")

    c = get("postgres")
    with c.connection():
        pass
    assert collector.get("connections") is not None
    assert calls["count"] >= 1


def test_begin_sql_defaults_for_unknown_isolation():
    # Unknown isolation should map to READ COMMITTED and READ WRITE unless readonly
    from auto_workflow.connectors.postgres import _begin_sql

    s = _begin_sql(isolation="nonsense", readonly=False, deferrable=False)
    up = s.upper()
    assert "READ COMMITTED" in up and "READ WRITE" in up


def test_error_mapping_lock(monkeypatch):
    class PoolBoom:
        @contextmanager
        def connection(self):
            raise RuntimeError("could not obtain lock on relation")
            yield  # pragma: no cover

    inject_psycopg(monkeypatch, PoolBoom())
    c = get("postgres")
    with pytest.raises(Exception) as ei:
        c.query("select 1")
    assert "transient" in str(ei.value).lower()


def test_sqlalchemy_dsn_uses_connect_args(monkeypatch):
    collector: dict = {}
    pool = PoolCapturing(collector)
    inject_psycopg(monkeypatch, pool)

    sa_collector: dict = {}

    class DummyEngine:
        def __init__(self, url, connect_args=None, **kwargs):
            sa_collector["url"] = url
            sa_collector["connect_args"] = connect_args or {}
            sa_collector["kwargs"] = kwargs

    class DummyMeta:
        def __init__(self):
            pass

    fake_sa = types.SimpleNamespace(
        create_engine=lambda url, **kw: DummyEngine(url, **kw), MetaData=lambda: DummyMeta()
    )

    def fake_sessionmaker(bind=None, **kw):
        class S:
            def __call__(self):
                return self

        return S()

    monkeypatch.setitem(pgmod.__dict__, "_ensure_sqlalchemy", lambda: (fake_sa, fake_sessionmaker))

    # Set DSN via JSON overlay
    monkeypatch.setenv(
        "AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__JSON",
        '{"dsn": "postgres://u:p@h:5432/d?sslmode=require"}',
    )

    c = get("postgres")
    _ = c.sqlalchemy_engine()
    assert sa_collector["url"].startswith("postgresql+psycopg://")
    assert sa_collector["connect_args"].get("dsn", "").startswith("postgres://")


def test_executemany_and_rowcount(monkeypatch):
    collector: dict = {}
    pool = PoolCapturing(collector)
    inject_psycopg(monkeypatch, pool)
    c = get("postgres")
    rc = c.executemany("insert into t(x) values(%(x)s)", [{"x": 1}, {"x": 2}, {"x": 3}])
    assert rc == 3


def test_fetch_modes(monkeypatch):
    collector: dict = {}
    pool = PoolCapturing(collector)
    inject_psycopg(monkeypatch, pool)
    c = get("postgres")
    one = c.query("select 1", fetch="one")
    assert one["x"] == 1
    many = c.query("select 1", fetch="many", size=2)
    assert len(many) == 2
    all_rows = c.query("select 1")
    assert len(all_rows) == 2


def test_query_iter_streaming(monkeypatch):
    collector: dict = {}
    pool = PoolCapturing(collector)
    inject_psycopg(monkeypatch, pool)

    # Override cursor to simulate finite batches
    orig_cursor = TxCursor.fetchmany

    def fetchmany(self, n):
        # first call -> 2 rows, second -> 1 row, then empty
        cnt = getattr(self, "_calls", 0)
        self._calls = cnt + 1
        if cnt == 0:
            return [{"x": 1}, {"x": 2}]
        if cnt == 1:
            return [{"x": 3}]
        return []

    monkeypatch.setattr(TxCursor, "fetchmany", fetchmany)
    try:
        c = get("postgres")
        out = list(c.query_iter("select generate_series(1,3)", size=2))
        assert [r["x"] for r in out] == [1, 2, 3]
    finally:
        monkeypatch.setattr(TxCursor, "fetchmany", orig_cursor)


def test_error_mapping_sqlstate(monkeypatch):
    class BoomError(RuntimeError):
        def __init__(self, code: str):
            super().__init__("oops")
            self.sqlstate = code

    class Pool:
        @contextmanager
        def connection(self):
            raise BoomError("40P01")  # deadlock
            yield  # pragma: no cover

    inject_psycopg(monkeypatch, Pool())
    c = get("postgres")
    with pytest.raises(Exception) as ei:
        c.query("select 1")
    assert "transient" in str(ei.value).lower()
