# Connectors

The `auto_workflow.connectors` package provides a lightweight registry and base contracts for
production-grade connectors. Postgres is available today, with S3 and ADLS2 planned next.

What’s available now:
- `auto_workflow.connectors.get(name, profile="default")` — retrieve a connector from the registry
- Base interfaces (`Connector`, `BaseConnector`) and error hierarchy (`ConnectorError`, etc.)
- Env/config overlay helpers with secret resolution via `auto_workflow.secrets`
- Postgres connector (psycopg3 pool-backed) with optional SQLAlchemy helpers

Install optional extras:

```bash
# Postgres connector runtime (psycopg3 + pool)
poetry install -E connectors-postgres

# SQLAlchemy helpers (engine/session/reflection)
poetry install -E connectors-sqlalchemy
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
