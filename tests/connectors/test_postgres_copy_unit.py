from __future__ import annotations

import io
import types
from contextlib import contextmanager

import pytest

from auto_workflow.connectors import get, reset


class DummyCopyIn:
    def __init__(self):
        self.buf = bytearray()
        self.rowcount = 3

    def write(self, b: bytes):
        self.buf.extend(b)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyCopyOut:
    def __init__(self):
        self._chunks = [b"a,b\n", b"1,2\n", b""]
        self.rowcount = 2

    def read(self, n: int):
        # pop from list to simulate stream
        return self._chunks.pop(0)

    def __iter__(self):  # pragma: no cover - fallback path
        yield from [b"a,b\n", b"1,2\n"]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyCursor:
    def __init__(self, mode: str):
        self.mode = mode

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchmany(self, n):  # pragma: no cover
        return []

    def copy(self, stmt):  # type: ignore[attr-defined]
        if "FROM STDIN" in stmt:
            return DummyCopyIn()
        return DummyCopyOut()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyConn:
    def __init__(self):
        self._stmts = []

    def execute(self, sql):
        self._stmts.append(sql)

    @contextmanager
    def cursor(self):
        yield DummyCursor("copy")


class DummyPool:
    @contextmanager
    def connection(self):
        yield DummyConn()

    def close(self):  # pragma: no cover
        pass


def inject_psycopg(monkeypatch):
    fake_psycopg = types.SimpleNamespace(rows=types.SimpleNamespace(dict_row=object()))
    fake_pool_mod = types.SimpleNamespace(ConnectionPool=lambda conninfo: DummyPool())
    import auto_workflow.connectors.postgres as pgmod

    monkeypatch.setitem(pgmod.__dict__, "_ensure_deps", lambda: (fake_psycopg, fake_pool_mod))


def setup_function(_):
    reset()
    import auto_workflow.connectors.postgres  # noqa: F401


def test_copy_from_with_iterable(monkeypatch):
    inject_psycopg(monkeypatch)
    c = get("postgres")
    chunks = [b"a,b\n", b"1,2\n"]
    rows = c.copy_from("public.t", chunks, columns=["a", "b"], delimiter=",")
    assert rows == 3


def test_copy_from_with_fileobj(monkeypatch):
    inject_psycopg(monkeypatch)
    c = get("postgres")
    f = io.BytesIO(b"a,b\n1,2\n")
    rows = c.copy_from("public.t", f)
    assert rows == 3


def test_copy_to_writes_to_file_like(monkeypatch):
    inject_psycopg(monkeypatch)
    c = get("postgres")
    out = io.BytesIO()
    rows = c.copy_to("public.t", out, columns=["a", "b"])
    assert rows == 2
    assert out.getvalue().startswith(b"a,b\n1,2\n")
