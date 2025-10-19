# Connectors

The `auto_workflow.connectors` package provides a lightweight registry and base contracts for
production-grade connectors. Postgres is available today, and ADLS2 (Azure Data Lake Storage Gen2)
is now available behind optional extras. S3 is planned next.

What’s available now:
- `auto_workflow.connectors.get(name, profile="default")` — retrieve a connector from the registry
- Base interfaces (`Connector`, `BaseConnector`) and error hierarchy (`ConnectorError`, etc.)
- Env/config overlay helpers with secret resolution via `auto_workflow.secrets`
- Postgres connector (psycopg3 pool-backed) with optional SQLAlchemy helpers
- ADLS2 connector (Azure Data Lake Storage Gen2) behind optional extras

Install optional extras:

```bash
# Postgres connector runtime (psycopg3 + pool)
poetry install -E connectors-postgres

# SQLAlchemy helpers (engine/session/reflection)
poetry install -E connectors-sqlalchemy

# ADLS2 connector runtime (Azure SDK)
poetry install -E connectors-adls2

# Install all available connector extras (Postgres, SQLAlchemy helpers, ADLS2)
poetry install -E connectors-all
```

Usage (Postgres):

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

End-to-end example (tasks + flow)

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

---

ADLS2 usage and configuration
-----------------------------

Install the ADLS2 extras and configure via env or `pyproject.toml`.

Install:

```bash
poetry install -E connectors-adls2
# or install all connector extras
poetry install -E connectors-all
```

Quick usage:

```python
from auto_workflow.connectors import adls2

with adls2.client("default") as fs:
	# Ensure container exists (convenience helper)
	fs.create_container("bronze", exist_ok=True)
	fs.make_dirs("bronze", "events/2025-10-19", exist_ok=True)
		fs.upload_bytes(
				container="bronze",
				path="events/2025-10-19/sample.csv",
				data=b"id,name\n1,alice\n",
				content_type="text/csv",
				overwrite=True,
		)
		rows = list(fs.list_paths("bronze", prefix="events/2025-10-19/"))
```

Auth & connection options (pick one):

- Connection string (recommended when available):
	- Env: `AUTO_WORKFLOW_CONNECTORS_ADLS2_<PROFILE>__CONNECTION_STRING="..."`
	- Aliases: `__CONN_STR`, `__DSN`
- Account URL + DefaultAzureCredential (AAD-based):
	- Env: `AUTO_WORKFLOW_CONNECTORS_ADLS2_<PROFILE>__ACCOUNT_URL="https://<acct>.dfs.core.windows.net"`
	- Env: `AUTO_WORKFLOW_CONNECTORS_ADLS2_<PROFILE>__USE_DEFAULT_CREDENTIALS=true`
- Custom credential object (advanced):
	- Provide via `pyproject.toml` or JSON overlay and pass through as `credential`.

Environment overrides (ADLS2):

Prefix: `AUTO_WORKFLOW_CONNECTORS_ADLS2_<PROFILE>__`

Examples (DEFAULT profile):

```bash
# Option A: single connection string
export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__CONNECTION_STRING="DefaultEndpointsProtocol=..."

# Option B: account_url + DefaultAzureCredential
export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__ACCOUNT_URL="https://myacct.dfs.core.windows.net"
export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__USE_DEFAULT_CREDENTIALS=true

# Optional tuning
export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__RETRIES__ATTEMPTS=5
export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__TIMEOUTS__CONNECT_S=2.0
export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__TIMEOUTS__OPERATION_S=30.0

# High-precedence JSON overlay
export AUTO_WORKFLOW_CONNECTORS_ADLS2_DEFAULT__JSON='{"connection_string":"..."}'
```

Notes:
- The client lazily imports Azure SDKs. If extras aren’t installed, an ImportError suggests `poetry install -E connectors-adls2`.
- `content_type` on upload is applied using Azure Blob `ContentSettings` under the hood.
- Errors are mapped to project exceptions: `AuthError`, `NotFoundError`, `TimeoutError`, `TransientError`, `PermanentError`.
- See `examples/adls_csv_flow.py` for a complete CSV roundtrip flow (container creation, folder, write/read, cleanup).
Convenience helpers

- `query_one(sql, params=None, timeout=None) -> dict | None`: returns the first row or None.
- `query_value(sql, params=None, timeout=None) -> Any | None`: returns first column of first row or None.

Pool tuning and connection parameters

- The client passes through optional pool parameters (if provided in cfg): `min_size`, `max_size`, `timeout`.
- `_conninfo` includes `application_name` if provided.
- `sslmode` is included only when explicitly configured (no default is forced); aligns with the SQLAlchemy URL builder behavior.

Transactions

- The connector ensures that all operations inside a `transaction()` block run on the same
	connection, with options applied at `BEGIN` time.

```python
from auto_workflow.connectors.postgres import client

with client("default") as db:
		with db.transaction(isolation="serializable", readonly=True, deferrable=True):
				db.execute("INSERT INTO t(v) VALUES (1)")
				# All statements in this block share the same connection and commit or rollback together
```

Notes:
- Nested `transaction()` blocks reuse the existing transaction (no additional BEGIN/COMMIT).
- Statement timeouts use `SET LOCAL statement_timeout` per connection.
- Prefer keeping the client open for the app lifecycle (registry caches the pool). Use
	`db.connection()` for connection-scoped work; avoid frequently closing the client to prevent
	pool thrash.

Pool lifecycle guidance

- The registry caches active clients per profile+config; avoid wrapping the client in a `with` block for each tiny operation in hot paths.
- Prefer:
	- `with client(profile).connection() as conn:` for scoped, multi-statement work, or
	- call `db.query/execute/...` without closing the client each time; close on application shutdown.
- Transactions (`db.transaction()`): statements inside the block run on the same connection; nested blocks do not re-BEGIN.

```

Configuration

Connector config is read from your `pyproject.toml` under `tool.auto_workflow.connectors`, then
overlaid by environment variables:

```toml
[tool.auto_workflow.connectors.postgres.default]
host = "db.example.com"
database = "app"
user = "appuser"
password = "secret://dev/db_password"  # resolved via secrets provider
```

Environment overrides use the prefix `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__`. You can also
provide a high‑precedence JSON overlay via `__JSON`:

```bash
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__HOST=localhost
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__JSON='{"sslmode": "require"}'
```

Notes:
- Providers are lazily imported and registered on first use (`get("postgres")`).
- The registry caches active clients per profile+config; closed clients are evicted automatically.
- Error mapping classifies timeouts, transient (e.g., deadlock/connection reset), and permanent errors.

Required vs optional settings (Postgres)

You can configure the client using either a single DSN or individual fields. The minimal requirements are:

- Option A (single variable): DSN
	- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__DSN`
	- Example: `postgresql://user:pass@host:5432/dbname` or `postgresql+psycopg://...`

- Option B (individual fields):
	- Required: `HOST`, `DATABASE` (or `DBNAME`), `USER`
	- Optional: `PASSWORD` (required if your server enforces password auth), `PORT` (defaults to 5432), `SSLMODE` (only applied if set), `APPLICATION_NAME` (for DB observability)

Notes:
- If you omit required fields with Option B, the connector’s low-level conninfo becomes empty and the underlying driver may fall back to libpq defaults; for predictable behavior, set either DSN or all required fields.
- The SQLAlchemy URL builder provides reasonable defaults (`localhost`, `postgres` user/database) if fields are omitted, but the connection may still fail if those defaults don’t match your environment.

Minimal env examples (DEFAULT profile)

```bash
# Option A: DSN only (recommended)
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__DSN="postgresql://app:secret@db:5432/appdb"

# Option B: individual fields
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__HOST=db
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__DATABASE=appdb
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__USER=app
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__PASSWORD=secret://dev/db_password  # resolved via secrets provider
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__PORT=5432                           # optional (default 5432)
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__SSLMODE=require                     # optional
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_DEFAULT__APPLICATION_NAME=auto-workflow      # optional
```

Environment variables reference (Postgres)

All variables use the prefix `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__`. The special key `__JSON` provides a high‑precedence JSON overlay.

- Connection fields
	- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__DSN` — single connection string. If set, individual fields are ignored.
	- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__HOST` — required if not using DSN
	- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__PORT` — optional, defaults to 5432
	- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__DATABASE` — required if not using DSN
	- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__DBNAME` — alias of DATABASE
	- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__USER` — required if not using DSN
	- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__PASSWORD` — optional, but required if your server enforces password auth (supports `secret://`)
	- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__SSLMODE` — optional; only applied if provided (for example: `require`)
	- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__APPLICATION_NAME` — optional; helps identify this app in DB logs/metrics
- Pool tuning (if supported by your psycopg_pool version)
	- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__MIN_SIZE`
	- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__MAX_SIZE`
	- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__TIMEOUT`
- High‑precedence JSON overlay
	- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_<PROFILE>__JSON` (example: `{"dsn": "postgresql://...", "sslmode": "require"}`)

Notes:
- JSON overlay has highest precedence; it can set any of the above keys.
- Secrets in env are resolved via the `auto_workflow.secrets` provider when they look like secrets (e.g., key name includes "password" or the value starts with `secret://`).
