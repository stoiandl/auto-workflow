"""Integration tests for Postgres connector with the flow/task API.

These tests are env-gated and require a running Postgres instance with the DSN provided via:

  export AUTO_WORKFLOW_CONNECTORS_POSTGRES_EXAMPLE__DSN="postgresql://user:pass@host:port/db"

They exercise:
- tasks/flows/fan_out orchestration
- transactions, execute/executemany/query/query_iter
- COPY to/from
- SQLAlchemy session/reflection (optional extra)
- logging middleware + events
- tracing spans
- caching and in-flight deduplication
- error mapping and statement timeout
"""

from __future__ import annotations

import io
import json
import os
import time
import uuid
from collections.abc import Iterable
from contextlib import asynccontextmanager
from typing import Any

import pytest

from auto_workflow import fan_out, flow, subscribe, task
from auto_workflow.connectors import postgres
from auto_workflow.connectors.exceptions import PermanentError, TimeoutError
from auto_workflow.metrics_provider import (
    InMemoryMetrics,
    get_metrics_provider,
    set_metrics_provider,
)
from auto_workflow.tracing import get_tracer, set_tracer

REQUIRED_ENV = "AUTO_WORKFLOW_CONNECTORS_POSTGRES_EXAMPLE__DSN"


def _env_ready() -> bool:
    return bool(os.getenv(REQUIRED_ENV))


skip_if_no_pg = pytest.mark.skipif(not _env_ready(), reason=f"integration requires {REQUIRED_ENV}")


@pytest.fixture(scope="module")
def profile() -> str:
    if not _env_ready():  # pragma: no cover - skip path
        pytest.skip(f"requires {REQUIRED_ENV}")
    return "example"


@pytest.fixture()
def db(profile: str):
    with postgres.client(profile) as c:
        yield c


"""
Note: logging, events, tracing, caching, and priority-only flow tests were moved
to tests/integration/flow/test_flow_core_integration.py to keep this file
focused strictly on Postgres + flow/task integration.
"""


def _unique_table(base: str) -> str:
    return f"{base}_{uuid.uuid4().hex[:8]}"


# --- Basic connector operations ---


@skip_if_no_pg
def test_basic_query_and_execute(db):
    t = _unique_table("aw_it_basic")
    db.execute(f"CREATE TABLE {t} (id SERIAL PRIMARY KEY, v INT NOT NULL)")
    assert db.execute(f"INSERT INTO {t} (v) VALUES (1)") == 1
    row = db.query(f"SELECT COUNT(*) AS n FROM {t}", fetch="one")
    assert int(row["n"]) == 1


@skip_if_no_pg
def test_executemany(db):
    t = _unique_table("aw_it_many")
    db.execute(f"CREATE TABLE {t} (v INT NOT NULL)")
    n = db.executemany(f"INSERT INTO {t} (v) VALUES (%s)", [(i,) for i in range(10)])
    assert n == 10


@skip_if_no_pg
def test_query_iter_streaming(db):
    t = _unique_table("aw_it_stream")
    db.execute(f"CREATE TABLE {t} (v INT NOT NULL)")
    db.executemany(f"INSERT INTO {t} (v) VALUES (%s)", [(i,) for i in range(250)])
    total = 0
    for r in db.query_iter(f"SELECT v FROM {t} ORDER BY v", size=32):
        total += int(r["v"])  # type: ignore[index]
    assert total == sum(range(250))


@skip_if_no_pg
def test_copy_from_iterable_and_copy_to_filelike(db):
    t = _unique_table("aw_it_copy")
    db.execute(f"CREATE TABLE {t} (a TEXT, b INT)")
    # copy from iterable of bytes
    rows = [b"x,1\n", b"y,2\n", b"z,3\n"]
    rc = db.copy_from(t, rows, columns=["a", "b"], format="csv")
    assert rc >= 0
    # export to buffer
    buf = io.BytesIO()
    rc2 = db.copy_to(t, buf, columns=["a", "b"], format="csv")
    assert rc2 >= 0 and len(buf.getvalue()) > 0


@skip_if_no_pg
def test_transaction_commit_and_rollback(db):
    t = _unique_table("aw_it_tx")
    db.execute(f"CREATE TABLE {t} (k INT PRIMARY KEY, v INT)")
    # commit
    with db.transaction():
        db.execute(f"INSERT INTO {t} (k, v) VALUES (1, 10)")
    assert db.query(f"SELECT COUNT(*) AS n FROM {t}", fetch="one")["n"] == 1
    # rollback
    with pytest.raises(PermanentError), db.transaction():
        db.execute(f"INSERT INTO {t} (k, v) VALUES (1, 20)")  # unique violation
        raise RuntimeError("force rollback")
    # still single row
    assert db.query(f"SELECT COUNT(*) AS n FROM {t}", fetch="one")["n"] == 1


@skip_if_no_pg
def test_error_mapping_unique_violation(db):
    t = _unique_table("aw_it_err")
    db.execute(f"CREATE TABLE {t} (k INT PRIMARY KEY)")
    db.execute(f"INSERT INTO {t} (k) VALUES (1)")
    with pytest.raises(PermanentError):
        db.execute(f"INSERT INTO {t} (k) VALUES (1)")


@skip_if_no_pg
def test_statement_timeout(db):
    with pytest.raises(TimeoutError):
        db.query("SELECT pg_sleep(1.0)", timeout=0.05)


# --- SQLAlchemy integration (optional) ---


@skip_if_no_pg
def test_sqlalchemy_session_basic(profile: str):
    try:
        with postgres.client(profile) as db, db.sqlalchemy_session() as session:  # type: ignore[attr-defined]
            t = _unique_table("aw_it_sa")
            session.execute(f"CREATE TABLE {t} (id SERIAL PRIMARY KEY, v INT)")
            session.execute(f"INSERT INTO {t} (v) VALUES (42)")
            rows = session.execute(f"SELECT v FROM {t}").fetchall()
            assert rows[0][0] == 42
    except ImportError:
        pytest.skip("sqlalchemy extra not installed")


@skip_if_no_pg
def test_sqlalchemy_reflect(profile: str):
    try:
        with postgres.client(profile) as db:
            md = db.sqlalchemy_reflect(schema="public")  # type: ignore[attr-defined]
            assert hasattr(md, "tables")
    except ImportError:
        pytest.skip("sqlalchemy extra not installed")


# --- Flow + Task orchestration ---


@skip_if_no_pg
def test_flow_with_tasks_simple(profile: str):
    t = _unique_table("aw_it_flow")

    @task
    def make_table():
        with postgres.client(profile) as c:
            c.execute(f"CREATE TABLE {t} (v INT)")

    @task
    def insert_vals(vals: list[int]):
        with postgres.client(profile) as c:
            c.executemany(f"INSERT INTO {t} (v) VALUES (%s)", [(v,) for v in vals])

    @task
    def sum_vals() -> int:
        with postgres.client(profile) as c:
            return int(c.query(f"SELECT COALESCE(SUM(v),0) AS s FROM {t}", fetch="one")["s"])

    @flow
    def f():
        make_table()
        insert_vals([1, 2, 3, 4])
        return sum_vals()

    assert f.run() == 10


@skip_if_no_pg
def test_fanout_concurrent_category_queries(profile: str):
    base = _unique_table("aw_it_cat")
    t = base

    @task
    def setup():
        with postgres.client(profile) as c:
            c.execute(f"CREATE TABLE {t} (cat TEXT, amount INT)")
            rows = [("a", 1), ("a", 2), ("b", 3), ("b", 4), ("c", 5)]
            c.executemany(f"INSERT INTO {t} (cat, amount) VALUES (%s, %s)", rows)

    @task
    def agg(cat: str) -> dict[str, Any]:
        with postgres.client(profile) as c:
            r = c.query(
                "SELECT %s AS cat, SUM(amount)::int AS total, COUNT(*)::int AS n FROM "
                f"{t} WHERE cat=%s GROUP BY cat",
                (cat, cat),
                fetch="one",
            )
            return {"cat": r["cat"], "total": r["total"], "n": r["n"]}

    @task
    def write(rows: Iterable[dict[str, Any]]):
        with postgres.client(profile) as c:
            ot = f"{base}_out"
            c.execute(f"CREATE TABLE {ot} (cat TEXT PRIMARY KEY, total INT, n INT)")
            c.executemany(
                f"INSERT INTO {ot} (cat, total, n) VALUES (%s, %s, %s)",
                [(r["cat"], r["total"], r["n"]) for r in rows],
            )
            return int(c.query(f"SELECT COUNT(*) AS n FROM {ot}", fetch="one")["n"])

    @flow
    def pipeline():
        setup()
        cats = ["a", "b", "c"]
        out = fan_out(agg, cats)
        return write(out)

    assert pipeline.run(max_concurrency=3) == 3


@skip_if_no_pg
def test_priority_affects_pg_tasks(profile: str):
    seen: list[str] = []
    # Track start order for only the two concurrent tasks
    subscribe(
        "task_started",
        lambda p: seen.append(p.get("task", "")) if p.get("task") in {"low", "high"} else None,
    )

    @task(name="setup")
    def setup():
        t = _unique_table("aw_it_prio")
        with postgres.client(profile) as c:
            c.execute(f"CREATE TABLE {t} (v INT)")
        return t

    @task(name="low", priority=0)
    def low(tbl: str):
        with postgres.client(profile) as c:
            c.executemany(f"INSERT INTO {tbl} (v) VALUES (%s)", [(i,) for i in range(2)])
        seen.append("low")
        return 0

    @task(name="high", priority=10)
    def high(tbl: str):
        with postgres.client(profile) as c:
            c.executemany(f"INSERT INTO {tbl} (v) VALUES (%s)", [(i,) for i in range(2, 4)])
        seen.append("high")
        return 1

    @flow
    def f():
        tbl = setup()
        return [low(tbl), high(tbl)]

    assert f.run(max_concurrency=2) == [0, 1]
    assert seen and seen[0] == "high"


@skip_if_no_pg
def test_copy_large_data_streaming(db):
    t = _unique_table("aw_it_copy2")
    db.execute(f"CREATE TABLE {t} (v INT)")
    db.executemany(f"INSERT INTO {t} (v) VALUES (%s)", [(i,) for i in range(5000)])
    buf = io.BytesIO()
    rc = db.copy_to(t, buf, columns=["v"], format="csv")
    assert rc >= 0
    assert len(buf.getvalue()) > 1000
