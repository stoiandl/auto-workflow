"""
Postgres fan-out flow example using tasks, flows, and optional SQLAlchemy ORM.

What it demonstrates
- Using @task and @flow to orchestrate Postgres work
- Dynamic fan-out to run multiple queries concurrently
- Creating tables via SQLAlchemy ORM if installed (falls back to raw SQL)
- Writing and reading results back to Postgres

Prerequisites
- Install extras:
    pip install "auto-workflow[connectors-postgres]"
  Optional (for ORM):
    pip install "auto-workflow[connectors-sqlalchemy]"
- Provide a DSN via environment overrides for the profile "example", e.g.:
    export AUTO_WORKFLOW_CONNECTORS_POSTGRES_EXAMPLE__DSN="postgresql://postgres:postgres@localhost:5432/postgres"

Run
  python examples/postgres_fanout_flow.py
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Any

from auto_workflow import fan_out, flow, task
from auto_workflow.connectors import postgres

PROFILE = os.getenv("PG_PROFILE", "example")


# --- Optional ORM model declarations (used only if SQLAlchemy is installed) ---
try:  # guarded import so example works without SQLAlchemy
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

    class Base(DeclarativeBase):
        pass

    class EtlInput(Base):  # type: ignore[misc, valid-type]
        __tablename__ = "etl_input"
        id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
        category: Mapped[str]
        amount: Mapped[float]

    class EtlSummary(Base):  # type: ignore[misc, valid-type]
        __tablename__ = "etl_summary"
        category: Mapped[str] = mapped_column(primary_key=True)
        total: Mapped[float]
        count: Mapped[int]

    HAVE_SA = True
except Exception:  # noqa: BLE001 - missing optional dependency is fine
    Base = None  # type: ignore[assignment]
    EtlInput = None  # type: ignore[assignment]
    EtlSummary = None  # type: ignore[assignment]
    HAVE_SA = False


@task
def ensure_schema(profile: str = PROFILE) -> None:
    """Create the input and summary tables if they don't exist.

    Uses SQLAlchemy ORM if available, otherwise falls back to raw SQL.
    """
    with postgres.client(profile) as db:
        if HAVE_SA and Base is not None:  # ORM path
            try:
                engine = db.sqlalchemy_engine()  # type: ignore[attr-defined]
                Base.metadata.create_all(engine)  # type: ignore[union-attr]
                return
            except ImportError:
                # Fallback to raw SQL if the sqlalchemy extra isn't installed
                pass
        # Raw DDL path
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS etl_input (
                id SERIAL PRIMARY KEY,
                category TEXT NOT NULL,
                amount NUMERIC NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS etl_summary (
                category TEXT PRIMARY KEY,
                total NUMERIC NOT NULL,
                count INT NOT NULL
            )
            """
        )


@task
def seed_input(profile: str = PROFILE) -> list[str]:
    """Seed the input table and return the list of categories present."""
    rows = [
        ("alpha", 10.0),
        ("alpha", 15.0),
        ("beta", 7.0),
        ("beta", 3.0),
        ("gamma", 5.0),
    ]
    with postgres.client(profile) as db:
        if HAVE_SA and EtlInput is not None:
            try:
                with db.sqlalchemy_session() as session:  # type: ignore[attr-defined]
                    session.execute("DELETE FROM etl_input")
                    session.add_all([EtlInput(category=c, amount=a) for c, a in rows])  # type: ignore[call-arg]
                    session.commit()
            except ImportError:
                # Fallback to raw SQL
                db.execute("DELETE FROM etl_input")
                db.executemany("INSERT INTO etl_input (category, amount) VALUES (%s, %s)", rows)
        else:
            db.execute("DELETE FROM etl_input")
            db.executemany("INSERT INTO etl_input (category, amount) VALUES (%s, %s)", rows)
    return sorted({c for c, _ in rows})


@task
def query_stats_for_category(category: str, profile: str = PROFILE) -> dict[str, Any]:
    """Query aggregated stats for a category."""
    with postgres.client(profile) as db:
        row = db.query(
            """
            SELECT %s AS category,
                   SUM(amount)::float AS total,
                   COUNT(*)::int AS count
            FROM etl_input
            WHERE category = %s
            GROUP BY category
            """,
            (category, category),
            fetch="one",
        )
    # row is a Mapping[str, Any]
    return {"category": row["category"], "total": row["total"], "count": row["count"]}


@task
def upsert_summary(rows: Iterable[dict[str, Any]], profile: str = PROFILE) -> int:
    """Write aggregated results into the summary table. Returns number of rows written."""
    payload = [(r["category"], float(r["total"]), int(r["count"])) for r in rows]
    with postgres.client(profile) as db:
        if HAVE_SA and EtlSummary is not None:
            try:
                with db.sqlalchemy_session() as session:  # type: ignore[attr-defined]
                    session.execute("DELETE FROM etl_summary")
                    session.bulk_save_objects(
                        [
                            EtlSummary(category=c, total=t, count=n)  # type: ignore[call-arg]
                            for (c, t, n) in payload
                        ]
                    )
                    session.commit()
                    return len(payload)
            except ImportError:
                pass
        db.execute("DELETE FROM etl_summary")
        db.executemany(
            "INSERT INTO etl_summary (category, total, count) VALUES (%s, %s, %s)",
            payload,
        )
        return len(payload)


@task
def read_summary(profile: str = PROFILE) -> list[dict[str, Any]]:
    with postgres.client(profile) as db:
        return db.query(
            "SELECT category, total::float AS total, count::int AS count "
            "FROM etl_summary ORDER BY category"
        )


@flow
def postgres_fanout_flow(profile: str = PROFILE) -> list[dict[str, Any]]:
    # Prepare schema and seed data
    ensure_schema(profile)
    categories = seed_input(profile)

    # Fan-out: run category queries concurrently
    stats = fan_out(query_stats_for_category, categories)

    # Write results and then read them out for a final return value
    upsert_summary(stats, profile)
    return read_summary(profile)


if __name__ == "__main__":
    print("Running Postgres fan-out flow with profile:", PROFILE)
    try:
        result = postgres_fanout_flow.run(PROFILE)
        print("Summary rows:", result)
    except Exception as e:
        print("Example failed:", e)
        print(
            "Hint: ensure Postgres is reachable and DSN is set via "
            "AUTO_WORKFLOW_CONNECTORS_POSTGRES_EXAMPLE__DSN"
        )
