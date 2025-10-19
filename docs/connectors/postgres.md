# Postgres Connector

The Postgres connector provides a psycopg3-backed client with connection pooling and convenient helpers. Optional SQLAlchemy helpers are available.

## Installation

Install optional extras:

```bash
poetry install -E connectors-postgres
poetry install -E connectors-sqlalchemy
# or install all connector extras
poetry install -E connectors-all
```

## Quick usage

```python
from auto_workflow.connectors.postgres import client

# Simple query
with client("default") as db:
    rows = db.query("select * from users where id = %s", (123,))

# SQLAlchemy session
with client("default").sqlalchemy_session() as session:
    # ORM usage here
    pass

# Reflect tables
md = client("default").sqlalchemy_reflect(schema="public", only=["users"])
users_table = md.tables["public.users"]

# Stream results (memory-friendly)
for row in client("default").query_iter("select * from big_table", size=1000):
    process(row)

# Bulk COPY (CSV)
import io
csv_data = io.BytesIO(b"a,b\n1,2\n")
client("default").copy_from("public.t", csv_data, columns=["a","b"], format="csv")
buf = io.BytesIO()
client("default").copy_to("public.t", buf, columns=["a","b"], format="csv")
```

## End-to-end example (tasks + flow)

```python
from auto_workflow import task, flow
from auto_workflow.connectors import postgres

PROFILE = "example"

@task
def setup(profile: str = PROFILE) -> str:
    t = "aw_docs_demo"
    with postgres.client(profile) as db:
        db.execute(f"CREATE TABLE IF NOT EXISTS {t} (v INT)")
    return t

@task
def insert_vals(tbl: str, profile: str = PROFILE):
    with postgres.client(profile) as db:
        db.executemany(f"INSERT INTO {tbl} (v) VALUES (%s)", [(i,) for i in range(5)])

@task
def sum_vals(tbl: str, profile: str = PROFILE) -> int:
    with postgres.client(profile) as db:
        return int(db.query_value(f"SELECT COALESCE(SUM(v),0) FROM {tbl}"))

@flow
def demo_flow(profile: str = PROFILE) -> int:
    t = setup(profile)
    insert_vals(t, profile)
    return sum_vals(t, profile)

if __name__ == "__main__":
    print(demo_flow.run(PROFILE))
```

## Convenience helpers

- `query_one(sql, params=None, timeout=None) -> dict | None`: returns the first row or None.
- `query_value(sql, params=None, timeout=None) -> Any | None`: returns first column of first row or None.

## Pool tuning and connection parameters

- Optional pool parameters (if provided in cfg): `min_size`, `max_size`, `timeout`.
- `_conninfo` includes `application_name` if provided.
- `sslmode` is included only when explicitly configured (aligns with SQLAlchemy URL behavior).

## Transactions

- All operations inside `transaction()` run on the same connection; nested transactions do not issue additional `BEGIN/COMMIT`.
- Statement timeouts use `SET LOCAL statement_timeout` per connection.

```python
from auto_workflow.connectors.postgres import client

with client("default") as db:
    with db.transaction(isolation="serializable", readonly=True, deferrable=True):
        db.execute("INSERT INTO t(v) VALUES (1)")
```

## Pool lifecycle guidance

- The registry caches active clients per profile+config; avoid opening/closing per tiny operation in hot paths.
- Prefer:
  - `with client(profile).connection() as conn:` for scoped, multi-statement work, or
  - keep the client open; close on application shutdown.

## Configuration

Connector config is read from your `pyproject.toml` under `tool.auto_workflow.connectors`, then overlaid by environment variables.

```toml
[tool.auto_workflow.connectors.postgres.default]
host = "db.example.com"
database = "app"
user = "appuser"
password = "secret://dev/db_password"  # resolved via secrets provider
```

Environment overrides use the prefix `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__`. You can also provide a high‑precedence JSON overlay via `__JSON`.

```bash
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__HOST=localhost
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__JSON='{"sslmode": "require"}'
```

### Required vs optional settings

You can configure the client using either a single DSN or individual fields.

- Option A (single variable): `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__DSN`
- Option B (individual fields): `HOST`, `DATABASE` (or `DBNAME`), `USER`; optional `PASSWORD`, `PORT`, `SSLMODE`, `APPLICATION_NAME`.

Minimal env examples (DEFAULT profile):

```bash
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__DSN="postgresql://app:secret@db:5432/appdb"
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__HOST=db
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__DATABASE=appdb
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__USER=app
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__PASSWORD=secret://dev/db_password
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__PORT=5432
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__SSLMODE=require
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__APPLICATION_NAME=auto-workflow
```

### Environment variables reference

- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__DSN` — single connection string. If set, individual fields are ignored.
- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__HOST` — required if not using DSN
- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__PORT` — optional, defaults to 5432
- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__DATABASE` — required if not using DSN
- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__DBNAME` — alias of DATABASE
- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__USER` — required if not using DSN
- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__PASSWORD` — optional; supports `secret://`
- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__SSLMODE` — optional
- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__APPLICATION_NAME` — optional
- High‑precedence JSON overlay: `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__JSON`
