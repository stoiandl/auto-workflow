# Connectors

The `auto_workflow.connectors` package provides a lightweight registry and base contracts for production-grade connectors.

Available connectors:

- [Postgres](connectors/postgres.md)
- [ADLS2](connectors/adls2.md)

Install optional extras:

```bash
poetry install -E connectors-postgres
poetry install -E connectors-sqlalchemy
poetry install -E connectors-adls2
# or everything:
poetry install -E connectors-all
```
