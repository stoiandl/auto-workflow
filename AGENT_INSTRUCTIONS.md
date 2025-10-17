# Agent Contribution Instructions

This document tells an automated coding agent exactly how to contribute a change to this repository, end‑to‑end, with the same gates our CI enforces plus a few stricter local rules.

Use these steps for every PR. Keep changes small and focused.

## Ground rules

- Single-scope PRs only:
  - One feature OR one bugfix per PR (no drive‑by refactors or unrelated formatting changes)
  - Keep diffs small and readable; split follow‑ups into separate PRs
- Documentation first‑class:
  - Update `docs/` and `README.md` for user‑visible changes
  - Update `CHANGELOG.md` under the `[Unreleased]` section using Keep a Changelog style
- Tests:
  - All existing tests must pass
  - New/changed behavior must be covered to 100% for the new code paths
  - Overall project coverage must remain ≥ 90% (CI gate)
- Style & static checks:
  - Ruff is the single source of truth for linting/formatting
  - Pre‑commit hooks must be run on all files before pushing
- Versioning:
  - Do NOT bump versions; maintainers handle releases and tagging
- Security & licensing:
  - Never commit secrets
  - Code is GPL‑3.0‑or‑later; your contributions are under the same license

## Environment and tooling

- Python 3.12+
- Poetry for dependency management
- Ruff for lint/format; pytest for tests; MkDocs for docs

Use the existing .venv if present (preferred), or create one if missing:

```zsh
# If .venv exists, just activate it and sync dev deps
if [ -d .venv ]; then
  source .venv/bin/activate
  poetry install --with dev
else
  # Create an in-project .venv without changing global Poetry config
  POETRY_VIRTUALENVS_IN_PROJECT=1 poetry install --with dev
  source .venv/bin/activate
fi

# Install git hooks using the .venv interpreter
pre-commit install
```

Sanity check the install (inside the activated .venv):

```zsh
which python
# Expect: .../auto-workflow/.venv/bin/python

ruff --version
pytest -q -k smoke || true  # ok if no explicit smoke tests exist
mkdocs --version
```

## Standard workflow for a PR

1) Branching
- Create a branch from `main` using a descriptive, single‑scope name:
  - feat/<short-scope> or fix/<short-scope> or docs/<short-scope>

2) Implement the change
- Keep public APIs stable; if you must change them, call it out in the PR and changelog
- Prefer typed Python; keep lines ≤ 100 chars (see Ruff config)
- Touch only files needed for this scope (source + tests + docs)

3) Update docs & changelog
- `docs/` pages relevant to your change (and examples in `examples/` if appropriate)
- `README.md` if surface behavior or usage changes
- `CHANGELOG.md`: add an entry under `[Unreleased]` with Added/Changed/Fixed subsections

4) Add tests (100% for new behavior)
- Place tests under `tests/` in an appropriate suite. Use existing markers where relevant:
  - core, scheduler, dynamic, caching, artifacts, observability, cli, benchmark, regression
- Aim for 100% coverage of new/changed code paths; exercise success, failure, and edge cases

5) Run quality gates locally (must all pass)

```zsh
# Lint & format (non-destructive check)
ruff check .
ruff format --check .

# Full test run with branch coverage and detailed missing lines
rm -f .coverage .coverage.* coverage.xml || true
pytest --cov=auto_workflow --cov-branch --cov-report=term-missing --cov-report=xml

# Pre-commit across the repo (applies fixes for Ruff hooks etc.)
pre-commit run --all-files

# Build docs in strict mode (fail on warnings)
mkdocs build --strict
```

Acceptance criteria for this step:
- Ruff outputs no errors; formatting matches
- pytest exits 0 and reports overall coverage ≥ 90%
- No missing lines in the new/changed code (target 100% feature coverage)
- Pre‑commit finishes with no failures
- MkDocs build succeeds

6) Smoke test the CLI (optional but recommended)

```zsh
python -m auto_workflow -h
auto-workflow -h  # console script (installed in .venv/bin)
```

7) Push and open a PR
- Keep the PR description concise; include:
  - What changed, why, and how it’s tested
  - Any docs links/screenshots (if relevant)
  - A checklist copy (below)

## PR checklist (copy into your PR)

- [ ] Single‑scope change (one feature/bugfix)
- [ ] Docs updated (docs/, README) and examples if applicable
- [ ] CHANGELOG.md updated under [Unreleased]
- [ ] Tests added/updated; new behavior covered to 100%
- [ ] All tests pass locally; overall cov ≥ 90%
- [ ] Ruff check and format pass
- [ ] Pre‑commit run on all files
- [ ] MkDocs site builds with --strict

## Testing guidance for agents

- Structure tests near similar suites; follow existing patterns and fixtures
- Use pytest markers when relevant (e.g., `@pytest.mark.dynamic` for fan‑out)
- Exercise edge cases:
  - empty/null inputs
  - timeouts/retries/failure policy interactions
  - concurrency limits and ordering in fan‑out/fan‑in scenarios
  - caching/artifact toggles and cache TTLs
- Prefer parameterized tests for concise coverage of variants
- For async tests, rely on `pytest-asyncio` (configured in `pyproject.toml`)
- Validate observability hooks (events, tracing, metrics) when changes affect them

Quick targeted runs during development:
```zsh
# Run a single test node
pytest tests/core/test_basic.py::test_simple_flow -q

# Run by marker
pytest -m dynamic -q
```

## Style, structure, and public API

- Type hints encouraged; keep public APIs explicit via `__all__` where applicable
- Follow the repo’s structure:
  - `auto_workflow/` — library source (keep modules cohesive and small)
  - `tests/` — tests grouped by domain/feature
  - `docs/` — MkDocs content (Material theme)
- Import sorting and formatting are enforced by Ruff (see `pyproject.toml`)
- Don’t rely on global mutable state; prefer explicit dependency passing

## Documentation

- All user‑visible changes must be documented:
  - Update or add pages in `docs/` (e.g., features, configuration, examples)
  - Ensure the site builds locally: `poetry run mkdocs build --strict`
  - For large changes, add brief snippets to `README.md` to keep it accurate

## Changelog conventions

We follow Keep a Changelog and SemVer. For PRs, update `CHANGELOG.md` under `[Unreleased]` using:

- Added — for new features
- Changed — for behavior changes
- Fixed — for bug fixes

Do not alter past released sections; maintainers handle release versioning and tagging.

## CI parity and enforcement

Our GitHub Actions CI runs on PRs and main:
- Lint (Ruff), format check
- Tests with branch coverage; coverage report uploaded to Codecov
- Coverage gates: project and patch targets are 90% (see `codecov.yml`)
- Pre‑commit on all files
- Docs build on main for the site

Locally, you mirror these steps with the commands in the "Run quality gates" section. Aim higher locally (100% for new code) so CI easily passes.

## Command cheat sheet

```zsh
# Activate existing .venv (or create if missing)
if [ -d .venv ]; then
  source .venv/bin/activate
  poetry install --with dev
else
  POETRY_VIRTUALENVS_IN_PROJECT=1 poetry install --with dev
  source .venv/bin/activate
fi

# Lint/format
ruff check .
ruff format .    # to apply formatting

# Tests + coverage
pytest --cov=auto_workflow --cov-branch --cov-report=term-missing

# Pre-commit (all files)
pre-commit run --all-files

# Docs
mkdocs serve                 # live preview
mkdocs build --strict

# CLI smoke
python -m auto_workflow -h
auto-workflow -h
```

## What not to do

- Don’t bundle multiple features in one PR
- Don’t bump versions or push tags
- Don’t decrease coverage or skip tests without a strong reason
- Don’t introduce new runtime dependencies lightly; discuss first if needed

---

If something blocks you (API uncertainty, test flakiness, missing fixtures), open an issue or draft PR describing the approach and what you need clarified.
