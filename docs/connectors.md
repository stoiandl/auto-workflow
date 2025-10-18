# Connectors (Scaffolding)

Status: scaffolding in this release. The `auto_workflow.connectors` package introduces the
base contracts, error types, registry, and configuration overlay utilities for
production-grade connectors (Postgres, S3, ADLS2).

What’s available now:
- `auto_workflow.connectors.get(name, profile="default")` — retrieve a connector from the registry
- Base interfaces (`Connector`, `BaseConnector`) and error hierarchy (`ConnectorError`, etc.)
- Env/config overlay helpers with secret resolution via `auto_workflow.secrets`

What’s coming next (behind optional extras, no new default deps):
- Postgres client (psycopg3 pool-backed)
- S3 client (boto3)
- ADLS2 client (azure-storage-file-datalake)

Notes:
- This scaffolding is dependency-free; concrete providers will be added incrementally.
- See `features/production-connectors.md` for the full design and rollout plan.
