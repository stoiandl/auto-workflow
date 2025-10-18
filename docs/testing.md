# Local Testing and Postgres via Docker Compose

This project ships a simple Docker Compose file to spin up a local Postgres for integration testing and examples.

## Start Postgres

```bash
docker compose -f test_helpers/docker-compose.yml up -d
```

This starts a `postgres:16-alpine` container on port 5432 with user/password `postgres` and database `postgres`.

Wait until it’s healthy (Compose healthcheck is configured), or run:

```bash
./test_helpers/wait-for-postgres.sh 127.0.0.1 5432
```

## Configure the DSN

Set the DSN env var used by tests and examples (profile "example"):

```bash
export AUTO_WORKFLOW_CONNECTORS_POSTGRES_EXAMPLE__DSN="postgresql://postgres:postgres@localhost:5432/postgres"
```

## Run integration tests

Run only the Postgres integration suite:

```bash
pytest -q tests/integration/postgres/test_postgres_flow_integration.py
```

Or run the whole test suite; env-gated integration tests will run if the DSN is set, otherwise they will skip:

```bash
pytest -q
```

## Try the flow examples

Run the fan-out flow example:

```bash
python examples/postgres_fanout_flow.py
```

Optionally install SQLAlchemy extras to use ORM helpers:

```bash
pip install "auto-workflow[connectors-sqlalchemy]"
```
