# Builder Agent (Production‑grade)

Stricter rules for a critical, production project. Your changes must be safe, small,
reversible, observable, and covered. Treat this as the single source of truth for
Builder Agent behavior.

## Golden rules
- Single‑scope PR only (one feature OR one bugfix). No drive‑by refactors.
- Backward compatibility by default. If a public API must change, add a deprecation
  window and call it out prominently in the PR and changelog.
- Zero hidden side effects. No global state mutations outside explicit lifecycle hooks.
- No new runtime dependencies without explicit approval. Dev‑only deps allowed if
  justified and documented.
- All behavior must be documented and observable (events/tracing/metrics where relevant).

## Environment
- Python 3.12+, Poetry for deps, in‑project `.venv`.
- Hooks must be installed and run from the project env.

```zsh
# If .venv exists, activate and sync dev deps; else create in‑project env
if [ -d .venv ]; then
  source .venv/bin/activate && poetry install --with dev
else
  POETRY_VIRTUALENVS_IN_PROJECT=1 poetry install --with dev && source .venv/bin/activate
fi
pre-commit install
```

## Planning & scope
- For non‑trivial work, include a short "Design notes" section in the PR description
  covering approach, alternatives considered, and risks/rollout.
- Feature‑flag risky behavior behind defaults‑off config where practical.
- Update `CHANGELOG.md` under `[0.1.2] - Unreleased` with clear Added/Changed/Fixed.

## Compatibility & API policy
- Do not break public APIs silently. Use deprecations with clear migration notes.
- Keep function signatures typed; prefer explicit return types.
- Avoid widening types with `Any` unless unavoidable; justify in code comments.

## Security & safety
- No secrets or tokens in code, tests, or fixtures.
- No network calls in unit tests; tests must be deterministic and hermetic.
- Avoid unbounded concurrency or resource usage; guard with limits and timeouts.

## Observability
- If events/tracing/metrics are impacted, update or add tests that assert emitted signals.
- Ensure span names and attributes remain stable and meaningful.

## Performance expectations
- Avoid O(n^2) behavior on hot paths; prefer linear or amortized approaches.
- If touching scheduler/flow/dag hot paths, run/extend `benchmarks/` and note results
  in the PR description. Avoid performance regressions.

## Testing policy (stricter)
- All existing tests must pass.
- New/changed code paths require:
  - Unit tests exercising success, failure, and boundary conditions.
  - Concurrency/async tests where applicable (timeouts, retries, ordering).
  - Determinism: no sleeps for timing except minimal, and seed randomness.
- Coverage targets:
  - Overall coverage: ≥ 92% locally (CI gate is 90%).
  - New/changed lines: effectively 100% (aim to eliminate uncovered lines in diff).

## Implementation workflow
1) Branch from `main`: `feat/<scope>` | `fix/<scope>` | `docs/<scope>`.
2) Implement minimal cohesive changes in `auto_workflow/` (+ tests + docs).
3) Update docs in `docs/` and examples in `examples/` if behavior changes.
4) Update `CHANGELOG.md` under `[0.1.2] - Unreleased`.

## Quality gates (must all pass locally)
```zsh
# Style & format
ruff check .
ruff format --check .

# Tests + coverage (branch coverage)
rm -f .coverage .coverage.* coverage.xml || true
pytest --cov=auto_workflow --cov-branch --cov-report=term-missing --cov-report=xml

# Pre-commit (auto-fixes + policy checks)
pre-commit run --all-files

# Docs build (strict)
mkdocs build --strict
```
Acceptance criteria:
- Ruff passes; formatting matches repository style.
- pytest exits 0; overall coverage ≥ 92%; new code paths at 100% where practical.
- Pre‑commit passes with zero failures.
- MkDocs build succeeds with `--strict`.

## Commit & PR
- Commit only relevant files; never include generated artifacts.
- Commit message: concise scope + intent (Conventional Commits style encouraged).
- PR description must include: What/Why/How, risks/rollout, test coverage summary,
  and any benchmarks when touching hot paths.
- Include the project’s PR checklist.

## PR checklist (copy into your PR)
- [ ] Single‑scope change; no unrelated modifications
- [ ] Public API unchanged or deprecation path documented
- [ ] Docs updated (docs/, README) and examples if applicable
- [ ] CHANGELOG.md updated under [0.1.2] - Unreleased
- [ ] Tests added/updated; new behavior covered to 100%
- [ ] All tests pass locally; overall cov ≥ 92%
- [ ] Ruff check and format pass
- [ ] Pre‑commit run on all files
- [ ] MkDocs site builds with --strict
- [ ] (If applicable) Benchmarks run and no regressions

## What not to do
- Don’t bump versions or change CI gates.
- Don’t add runtime deps casually; avoid optional heavy transitive deps.
- Don’t introduce flaky, time‑sensitive, or networked tests.
