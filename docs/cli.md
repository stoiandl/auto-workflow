# Command Line Interface

A minimal CLI supports executing and introspecting flows.

## Run a Flow
```bash
python -m auto_workflow.cli run path.to.module:flow_name
```

## Describe a Flow (JSON)
```bash
python -m auto_workflow.cli describe path.to.module:flow_name
```

## List Flows in Module
```bash
python -m auto_workflow.cli list path.to.module
```

## Options
- `--failure-policy` (fail_fast | continue | aggregate)
- `--max-concurrency INT` (must be a positive integer)

### Errors & validation
- If the `module:object` cannot be imported or found, the CLI exits with a helpful error message.
- Invalid `--failure-policy` values are rejected.
- Non-positive values for `--max-concurrency` are rejected.

(Subject to enhancement; see roadmap.)
