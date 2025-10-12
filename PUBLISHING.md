# Publishing and Release Cheat Sheet (maintainers)

This project publishes to PyPI via GitHub Actions (PyPI Trusted Publishing). Do not upload locally.

Final releases go to PyPI when a tag `vX.Y.Z` is pushed. Release candidates (tags with `-rc`) go to TestPyPI.

## Pre-flight checklist

- On main, clean working tree
- `pyproject.toml` version is the release you intend (e.g., `0.1.0`)
- `CHANGELOG.md` and README are up to date
- CI is green on main

Optional local validation (no local uploads):

```zsh
# Lint/tests/coverage
poetry run ruff check . && poetry run ruff format --check .
poetry run pytest --cov=auto_workflow --cov-branch --cov-report=term-missing

# Build and check metadata/description
poetry build
poetry run twine check dist/*
```

## Cut a final release (PyPI)

```zsh
# Set version (if you need to bump)
# poetry version patch   # or: minor | major | 1.2.3

# Commit the version bump
# git add pyproject.toml CHANGELOG.md README.md
# git commit -m "release: v0.1.0"
# git push origin main

# Tag and push (publishes via CI)
export VERSION=0.1.0
# Signed tag recommended; use unsigned if you don’t have GPG configured
git tag -s v$VERSION -m "auto-workflow v$VERSION" || git tag v$VERSION -m "auto-workflow v$VERSION"
git push origin v$VERSION
```

The workflow `.github/workflows/pypi-flow.yml` will:
- build and test
- refuse to publish if the tag’s commit isn’t reachable from `main`
- publish to PyPI with Trusted Publishing
- create a GitHub Release on success

### Monitor and verify the PyPI release

```zsh
# Open the workflow runs page (optional)
open "https://github.com/stoiandl/auto-workflow/actions/workflows/pypi-flow.yml"

# After success, install from PyPI to verify
python -m venv .venv-rel && source .venv-rel/bin/activate
pip install --upgrade pip
pip install "auto-workflow==$VERSION"
python -m auto_workflow -h
auto-workflow -h
```

PyPI project page: https://pypi.org/project/auto-workflow/

## Cut a release candidate (TestPyPI)

```zsh
# Example RC version
export VERSION=0.1.1-rc1
poetry version $VERSION

git add pyproject.toml CHANGELOG.md
git commit -m "release: v$VERSION (rc)"
git push origin main

git tag -s v$VERSION -m "auto-workflow v$VERSION" || git tag v$VERSION -m "auto-workflow v$VERSION"
git push origin v$VERSION
```

RC tags (containing `-rc`) will publish to TestPyPI. Install from TestPyPI to verify:

```zsh
python -m venv .venv-rc && source .venv-rc/bin/activate
pip install --upgrade pip
pip install -i https://test.pypi.org/simple "auto-workflow==$VERSION"
python -m auto_workflow -h
auto-workflow -h
```

## Verify final release

```zsh
# Fresh venv sanity check from PyPI
python -m venv .venv-rel && source .venv-rel/bin/activate
pip install --upgrade pip
pip install "auto-workflow==0.1.0"
python - <<'PY'
import auto_workflow as aw
print('version:', getattr(aw, '__version__', 'unknown'))
print('api:', [n for n in ('task','flow','fan_out','get_context') if hasattr(aw,n)])
PY
python -m auto_workflow -h
auto-workflow -h
```

## Rollback / hotfix

- If something goes wrong, yank the version on PyPI, fix on `main`, bump version, retag, and republish.
- For RCs, delete the tag and cut a new `-rcN`.

## Notes

- Publishing is CI-only. Local `twine upload` is not used.
- The workflow requires the tag to be on a commit reachable from `main`.
- Trusted Publishing is configured in PyPI for this repo: `stoiandl/auto-workflow`, workflow `pypi-flow.yml`.