# Postgres Fan-Out Flow

End-to-end example: `examples/postgres_fanout_flow.py`

This flow demonstrates:
- Creating tables (via SQLAlchemy if installed, or raw SQL fallback)
- Seeding data
- Dynamic fan-out to query per-category stats concurrently
- Upserting an aggregated summary
- Reading back the results

## Install

```bash
# Postgres connector
poetry install -E connectors-postgres
# Optional SQLAlchemy helpers (engine/session/ORM)
poetry install -E connectors-sqlalchemy
# or everything
poetry install -E connectors-all
```

## Environment (profile: EXAMPLE)

```bash
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_EXAMPLE__DSN="postgresql://postgres:postgres@127.0.0.1:5432/postgres"
```

Tip: In CI and local dev with Docker, the repo includes `test_helpers/docker-compose.yml` and a `wait-for-postgres.sh` script.

## Run

```bash
poetry run python examples/postgres_fanout_flow.py
```

Expected behavior:
- Creates `etl_input` and `etl_summary` tables if missing
- Seeds sample rows into `etl_input`
- Computes aggregates per category using fan-out
- Upserts into `etl_summary` and prints the summary rows

If SQLAlchemy is installed, the example will use ORM for schema and session; otherwise, it falls back to raw SQL.
