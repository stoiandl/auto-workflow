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
- `--max-concurrency INT`

(Subject to enhancement; see roadmap.)
