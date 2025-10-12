# Release plan for auto-workflow

This document outlines how we prepare and publish releases to PyPI using a GitHub Flow process with CI/CD, plus the checklists to keep README and docs aligned with the library’s current state.

Use this as a living checklist for each release. Update it whenever the process changes.

## Repo-specific TODOs before the first PyPI publish

- README:
  - Add a simple `pip install auto-workflow` section alongside Poetry dev install.
  - Replace "Basic CLI (Planned)" with actual CLI usage. Today, the CLI is available via `python -m auto_workflow ...`. Consider adding a console script for `auto-workflow` and reflect whichever approach you ship.
  - Use absolute URLs for images (PyPI won’t render repo-relative assets), or ensure assets are included in the sdist.
  - Tighten the "Status" wording to match current maturity (alpha). Avoid calling shipped features "planned".
- Packaging:
  - Consider adding a console script entry point in `pyproject.toml` under `[tool.poetry.scripts]` if you want `auto-workflow` on PATH.
  - Optionally include `auto_workflow/py.typed` and add the `Typing :: Typed` classifier if you intend to ship inline type hints.
  - Expand classifiers (Python 3.12, Environment :: Console, Development Status :: 3 - Alpha, etc.).
  - Optionally expose `__version__` in `auto_workflow/__init__.py` for easier introspection.
- CI/CD:
  - Add a release workflow triggered on tags (`v*`) using PyPI Trusted Publishing or API tokens.
  - Keep docs deploy workflow as-is; it already builds from main.

## Overview

- Branching model: GitHub Flow (feature branch -> PR -> main).
- Versioning: Semantic Versioning. Pre-1.0 may introduce breaking changes in minor releases; after 1.0, breaking changes only in majors.
- Artifacts: sdist and wheel built by CI.
- Publishing: GitHub Actions on tags. Optional pre-releases to TestPyPI.
- Docs: MkDocs site publishes from main; keep docs consistent with the released API.

## Pre-release checklist (must pass)

1) Version bump
- Decide bump (patch | minor | major) based on changes.
- Update `[tool.poetry].version` in `pyproject.toml` (e.g., via `poetry version patch`).
- Ensure the chosen tag will be `vX.Y.Z` (and matches the version in pyproject).

2) Changelog & release notes
- Add a `CHANGELOG.md` entry for `X.Y.Z` summarizing features, fixes, and breaking changes.
- Highlight migration notes if behavior changed.

3) README and docs audit
- README should include:
  - pip install instructions: `pip install auto-workflow`.
  - A minimal runnable example that works as-is.
  - CLI usage that matches what’s actually shipped (both `python -m auto_workflow` and console script, if provided).
  - Status and badges reflecting reality (alpha/beta/stable).
  - Links to docs, repo, and license.
  - Images that render on PyPI (absolute URLs or ensure assets are included in sdist).
- Docs site:
  - Build locally (`poetry run mkdocs build --strict`) and fix any warnings.
  - Ensure examples and pages reflect current APIs and behavior.

4) Public API surface
- `auto_workflow/__init__.py` should export only supported, documented symbols.
- Optional but recommended: expose `__version__` for easier introspection.
- If distributing inline type hints, consider adding `auto_workflow/py.typed` and the `Typing :: Typed` classifier.

5) Packaging sanity
- `pyproject.toml` metadata is accurate: name, description, readme, license, homepage, repository, documentation, classifiers, Python version.
- Runtime dependencies are minimal and have sensible version ranges.
- Ensure only necessary files are packaged (exclude large or generated artifacts like `site/` unless required at runtime).

6) Quality gates
- Lint and format with Ruff pass.
- Tests pass with coverage ≥ 90% (config in `pyproject.toml`).
- CI on PR is green.

## Local dry run (recommended before tagging)

- Clean build:
  - `poetry build`
- Validate long description & metadata:
  - `python -m twine check dist/*`
- Smoke test in a clean venv:
  - Create a venv, `pip install dist/*.whl`, then:
  - `python -c "import auto_workflow as aw; print('Imported', aw.__name__)"`

Optional TestPyPI drill:
- Upload to TestPyPI: `python -m twine upload --repository testpypi dist/*`
- Install back: `pip install -i https://test.pypi.org/simple auto-workflow==X.Y.Z`

## CI/CD pipeline design (GitHub Actions)

We publish on tags `v*`. Prefer PyPI Trusted Publishing; otherwise use an API token secret.

Suggested workflow file: `.github/workflows/pypi-flow.yml` (matches the PyPI pending Trusted Publisher configuration).

- Trigger: push on tag `v*`.
- Jobs:
  1) build: setup Python (3.12), install via Poetry, run lint/tests, then `poetry build` and upload `dist/` as an artifact.
  2) publish-testpypi (optional): if tag contains `-rc`, publish to TestPyPI.
  3) publish-pypi: if not a pre-release tag, publish to PyPI.

Example skeleton (adapt as needed):

```yaml
name: pypi-flow
on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install Poetry
        uses: abatilo/actions-poetry@v3
        with:
          poetry-version: '1.8.3'
      - name: Install deps
        run: poetry install --with dev --no-interaction --no-ansi
      - name: Lint
        run: |
          poetry run ruff check .
          poetry run ruff format --check .
      - name: Test
        run: poetry run pytest --cov=auto_workflow --cov-branch --cov-report=term-missing
      - name: Build
        run: poetry build
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/*

  publish-testpypi:
    if: contains(github.ref_name, '-rc')
    needs: build
    runs-on: ubuntu-latest
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist
      - name: Publish to TestPyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: https://test.pypi.org/legacy/
          print-hash: true

  publish-pypi:
    if: ${{ !contains(github.ref_name, '-rc') }}
    needs: build
    runs-on: ubuntu-latest
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          print-hash: true
```

To use Trusted Publishing, configure a Trusted Publisher for this repository/workflow in PyPI (and TestPyPI). In your PyPI project, ensure the pending publisher has:

- Repository: `stoiandl/auto-workflow`
- Workflow: `pypi-flow.yml`
- Environment name: (Any)

If using API tokens instead, set `PYPI_API_TOKEN` and `TEST_PYPI_API_TOKEN` secrets and remove the `id-token: write` permissions.

## Release procedure (CI only — no local uploads)

1) Prep a release PR:
- Apply the pre-release checklist.
- Commit version bump and changelog.
- Include README/docs changes.
- Merge on green CI.

2) Tag the release on main (publishing is CI-only):
- `git tag -s vX.Y.Z -m "auto-workflow vX.Y.Z"`
- `git push origin vX.Y.Z`

3) CI publishes to (Test)PyPI depending on tag (rc vs final).

4) Draft GitHub release notes
- Use the changelog entry. Link to docs and highlights.

5) Verify
- PyPI page renders README correctly; classifiers, version, and metadata look good.
- Install from PyPI in a clean venv and run a minimal example.

Note: The release workflow will refuse to publish if the tag is not on a commit reachable from `main`.

## Post-release

- Optionally bump version to next dev cycle (e.g., `X.Y.(Z+1)-dev`).
- Confirm docs site reflects the release (docs workflow runs on main).
- Announce release and update any external references.

## Quick audit checklists

README/docs
- [ ] pip install section present
- [ ] minimal runnable example works
- [ ] CLI docs match shipped behavior
- [ ] status/badges accurate
- [ ] links valid, images render on PyPI
- [ ] docs build clean locally and in CI
- [ ] examples runnable

Packaging
- [ ] pyproject metadata and classifiers accurate
- [ ] Python version floor matches tested versions
- [ ] only required files packaged (exclude site/, large assets)
- [ ] optional: `py.typed` present for inline typing
- [ ] optional: console script entry point defined
- [ ] `twine check` passes

Local validation
- [ ] `poetry build` succeeds
- [ ] `twine check` passes
- [ ] clean venv smoke test import + tiny flow run

## Handy commands (zsh)

```zsh
# Bump version (patch/minor/major)
poetry version patch

# Clean build
rm -rf dist/ build/
poetry build

# Check package metadata
python -m twine check dist/*

# Local install smoke test
python -m venv .venv-release && source .venv-release/bin/activate
pip install --upgrade pip
pip install dist/*.whl
python - <<'PY'
import auto_workflow as aw
print('auto_workflow version:', getattr(aw, '__version__', 'unknown'))
print('Public API:', [n for n in dir(aw) if n in {'task','flow','fan_out','get_context'}])
PY
```

---

If this plan diverges from actual automation, update this file in the same PR.
