# Contributing to auto-workflow

Thanks for your interest in contributing! This guide explains how to get a local dev environment running, coding standards, quality gates, and how to submit changes. Small fixes are welcome; larger proposals should start with an issue for discussion.

If you're an automated coding agent, please follow the stricter, step-by-step workflow in `agents/BUILDER_AGENT.md` and see `agents/REVIEWER_AGENT.md` for review guidelines.

## TL;DR
- Use Python 3.12+ and Poetry
- Lint and format with Ruff
- Tests with pytest; coverage minimum is 90%
- CI and Codecov must pass; PRs are coverage-gated
- Docs are built with MkDocs (Material theme)
 - For full test suite (including Postgres), install optional extras and Docker

## Getting set up

1) Fork and clone the repo, then create a feature branch.

2) Install dependencies with Poetry:

```bash
# Full local dev (includes dev tools and connector extras used in tests)
poetry install --with dev -E connectors-postgres -E connectors-sqlalchemy
```

3) (Optional) Install pre-commit hooks:

```bash
poetry run pre-commit install
```

4) Run the quick checks:

```bash
# Lint and format check
poetry run ruff format --check .
poetry run ruff check .

# Unit tests with coverage (branch coverage)
poetry run pytest --cov=auto_workflow --cov-branch --cov-report=term-missing
```

If you prefer a faster inner loop, you can run a subset of tests:

```bash
# By node id
poetry run pytest tests/core/test_basic.py::test_simple_flow
# By marker
poetry run pytest -m core -q
```

## Coding style and conventions

- Python: 3.12+ (typed where reasonable). Keep public API stable; breaking changes should be discussed first.
- Lint/format: Ruff manages linting and formatting. Run `ruff check .` and `ruff format .` before committing.
- Tests: Use pytest. Put new tests alongside existing suites under `tests/` and name modules `test_*.py`.
- Async: Prefer `async`/`await` where appropriate; use `pytest-asyncio` patterns in tests.
- Docs: If you change public behavior, add or update docs in `docs/` and ensure site builds locally.

## Database-backed tests (Postgres)

The test suite includes Postgres-backed integration tests. By default, our pytest hooks will:

- Start a local Postgres via Docker Compose (`test_helpers/docker-compose.yml`)
- Wait for readiness, then set the DSN env var for the "example" profile:
	- `AUTO_WORKFLOW_CONNECTORS_POSTGRES_EXAMPLE__DSN=postgresql://postgres:postgres@127.0.0.1:5432/postgres`

Control via environment variables:

- Set `AW_NO_DOCKER=1` to skip starting Docker Compose (useful if you provide your own DB)
- Set `AUTO_WORKFLOW_CONNECTORS_POSTGRES_EXAMPLE__DSN=...` to point tests at an external Postgres
- Set `AW_KEEP_DOCKER=1` to keep the Compose stack running after tests

Tip: You can also run just the Postgres integration suite:

```bash
poetry run pytest -q tests/integration/postgres/test_postgres_flow_integration.py
```

## Quality gates (must pass)

CI enforces the following before merge:
- Build: package installs via Poetry
- Lint: Ruff lint and format check
- Tests: pytest
- Coverage: 90% minimum using branch coverage (config in `pyproject.toml`)
- Codecov: project and patch coverage gates at 90% (see `codecov.yml`)

Locally you can replicate these gates with:

```bash
poetry run ruff format --check . && poetry run ruff check .
poetry run pytest --cov=auto_workflow --cov-branch --cov-report=term-missing
poetry run mkdocs build --strict
```

If coverage is below 90%, please add focused tests. You can view details in the terminal report and, in CI, via the Codecov PR comment.

## Making changes

1) Open (or find) an issue to describe the change if it’s non-trivial.
2) Create a feature branch; keep the changes focused and small.
3) Add or update tests to cover your changes.
4) Update docs for user-visible behavior changes.
5) Run the quality gates locally (see above).
6) Push and open a Pull Request.

### PR checklist
- [ ] Code compiles and linters pass
- [ ] Unit tests pass locally
- [ ] Coverage ≥ 90% (branch coverage)
- [ ] Docs updated (if applicable)
- [ ] Changelog entry (if a user-visible change; pending a formal CHANGELOG)
 - [ ] For connector changes: ensure integration tests run locally (see Postgres notes above)

### Commit messages
Use clear, descriptive messages. Conventional Commits style is welcome but not required. Example:
- chore: bump deps
- fix(scheduler): avoid deadlock on priority reschedule
- feat(cli): add `describe` command flags

## Docs (MkDocs)

Build the site locally to verify docs changes:

```bash
poetry run mkdocs serve
```

The CI will build and publish docs to GitHub Pages from the `main` branch.

## Project structure (high level)

- `auto_workflow/` — library source
- `tests/` — unit/integration tests
- `docs/` — user documentation (MkDocs)
- `.github/workflows/ci.yml` — CI pipeline
- `codecov.yml` — Codecov coverage gates for PRs

## Security and licensing

- Do not commit secrets. Use environment variables in tests where needed.
- This project is GPL‑3.0-or-later. By contributing, you agree to license your contributions under the same license.

## Getting help

- Open an issue for bugs and feature requests
- Start a discussion or comment on related issues for design proposals

Thanks again for contributing and helping improve auto-workflow!
