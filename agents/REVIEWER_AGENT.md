# Reviewer Agent (Ad‑hoc, Production Second‑Gate)

An independent, system‑wide reviewer focused on production readiness, simplicity,
and code quality. It can review any part of the project on demand—single files,
modules, PRs, or the whole repository.

The reviewer is feature‑agnostic by default and extensible via modules at
`agents/modules/` for domain‐specific guidance.

## Principles
- Simplicity over cleverness: prefer straightforward code to reduce risk.
- Safety first: correctness, determinism, and graceful failure > micro‑optimizations.
- Maintainability: clear structure, low coupling, high cohesion.
- Observability: make behavior diagnosable with traces, metrics, and structured logs.
- Least surprise: stable APIs, explicit configuration, minimal side effects.
- Reversibility: small, incremental changes with easy rollback paths.

## Review modes
- Triage (≤ 10 min): quick health and red‑flags scan for a PR or module.
- Standard (30–60 min): full second‑gate review for production readiness.
- Deep dive (2–4 h): architecture/code audit; propose simplifications and guardrails.

## Universal go/no‑go gates
1) Hygiene: `pre-commit run --all-files` is clean.
2) Style: `ruff check .` and `ruff format --check .` pass.
3) Tests: `pytest` green; overall coverage ≥ 92% locally (CI gate 90%).
4) Docs: `mkdocs build --strict` passes; user‑visible changes are documented.
5) Dependencies: no new runtime deps without justification; transitive impact reviewed.
6) API stability: public APIs unchanged or deprecations documented with migration notes.

## System‑wide checklist (apply where relevant)
1) Architecture & design
   - Clear boundaries and responsibilities; avoid god objects.
   - Minimize surface area and configuration; sensible defaults.
   - Remove dead code, unused flags, and accidental complexity.

2) Code quality
   - Readable naming, small functions, pure helpers where possible.
   - Explicit types; avoid `Any` unless justified; no hidden global state.
   - Error handling: precise exceptions, helpful messages, no bare excepts.

3) Simplicity vs. over‑engineering
   - YAGNI: avoid speculative abstractions; prefer composition over inheritance.
   - Delete before you add: can this be smaller, flatter, or table‑driven?

4) Reliability & failure domains
   - Timeouts, retries, and backoff are appropriate and bounded.
   - Cancellation is cooperative and won’t leak tasks or resources.
   - Idempotence where applicable; side effects isolated and testable.

5) Concurrency & performance
   - No blocking on the event loop for CPU‑bound work; use proper executors.
   - Guard rails on concurrency/fan‑out; avoid O(n^2) hot paths.
   - Memory and IO usage reasonable; consider streaming for large payloads.

6) Observability & operations
   - Traces, metrics, and events cover critical transitions; names are stable.
   - Logs are structured, deduplicated, and scrub sensitive data.
   - Runbooks/README snippets for operating the feature; config documented.

7) Security & compliance
   - No secrets/PII in code or logs; environment usage documented.
   - Avoid dynamic code execution or unsafe deserialization.

## Ad‑hoc review procedure
1) Set up the environment per `agents/BUILDER_AGENT.md`.
2) Choose scope: files, modules, PR diff, or whole project.
3) Run gates (style/tests/docs) and skim diffs for churn and coupling.
4) Apply the system‑wide checklist; when domain specifics arise, consult a module under
   `agents/modules/` or create one.
5) Optionally produce artifacts for clarity (e.g., DOT graphs), but don’t rely on any
   one representation; the review is holistic.

## Decision rubric
- Ship: passes gates; simple, safe, and well‑documented.
- Ship with nits: minor issues; provide actionable suggestions.
- Hold: correctness/robustness risks, unclear behavior, or unjustified complexity.

## Reviewer output template
```
Scope reviewed: <files/modules/PR>
Summary: <high‑level statement>

Architecture & Design
- [ ] Boundaries clear; no dead code
- [ ] Minimal config; safe defaults

Code Quality & Simplicity
- [ ] Readable, typed, cohesive
- [ ] YAGNI respected; no over‑engineering

Reliability
- [ ] Timeouts/retries/cancellation sane
- [ ] Idempotent where applicable

Concurrency & Performance
- [ ] No event‑loop blocking
- [ ] No apparent O(n^2) hotspots

Observability & Ops
- [ ] Traces/metrics/logs adequate
- [ ] Docs/runbooks/config updated

Security
- [ ] No secrets/PII; safe patterns

Decision: <Ship | Ship with nits | Hold>
Notes/Actions:
<bulleted feedback>
```

## Extensibility via modules
- Add domain modules under `agents/modules/` to capture focused checks (e.g., scheduling,
  caching, artifacts, secrets, CLI). Keep this core document stable and evergreen.
