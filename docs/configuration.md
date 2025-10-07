# Configuration

Configuration values are loaded from `pyproject.toml` under `[tool.auto_workflow]` merged with defaults and overridable via environment variables prefixed with `AUTO_WORKFLOW_`.

## Defaults
| Key | Default | Description |
|-----|---------|-------------|
| default_executor | async | Preferred execution mode when unspecified |
| log_level | INFO | Baseline logging level (middleware dependent) |
| max_dynamic_tasks | 2048 | Guardrail for dynamic expansion |
| artifact_store | memory | Artifact backend (memory/filesystem) |
| artifact_store_path | .aw_artifacts | Directory for file store |
| result_cache | memory | Result cache backend |
| result_cache_path | .aw_cache | Directory for file cache |

## Example pyproject.toml
```toml
[tool.auto_workflow]
artifact_store = "filesystem"
artifact_store_path = ".data/artifacts"
result_cache = "filesystem"
result_cache_path = ".data/cache"
max_dynamic_tasks = 4096
```

## Environment Overrides
```bash
export AUTO_WORKFLOW_RESULT_CACHE=filesystem
export AUTO_WORKFLOW_RESULT_CACHE_PATH=/tmp/aw_cache
```

## Reloading Config
```python
from auto_workflow.config import reload_config
reload_config()
```
Caches are cleared (using lru_cache invalidation).
