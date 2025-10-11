# Configuration

Configuration values are loaded from `pyproject.toml` under `[tool.auto_workflow]` merged with defaults and overridable via environment variables prefixed with `AUTO_WORKFLOW_`.

## Defaults
| Key | Default | Description |
|-----|---------|-------------|
| log_level | INFO | Baseline logging level (middleware dependent) |
| max_dynamic_tasks | 2048 | Guardrail for dynamic expansion |
| artifact_store | memory | Artifact backend (memory/filesystem) |
| artifact_store_path | .aw_artifacts | Directory for file store |
| artifact_serializer | pickle | Serializer for filesystem artifacts (pickle/json) |
| result_cache | memory | Result cache backend |
| result_cache_path | .aw_cache | Directory for file cache |
| result_cache_max_entries | None | Optional LRU bound for in-memory cache |
| process_pool_max_workers | None | Max workers for process pool |

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
# Logging controls
export AUTO_WORKFLOW_DISABLE_STRUCTURED_LOGS=1
export AUTO_WORKFLOW_LOG_LEVEL=DEBUG

# Process pool tuning
export AUTO_WORKFLOW_PROCESS_POOL_MAX_WORKERS=8

# Cache bounding
export AUTO_WORKFLOW_RESULT_CACHE_MAX_ENTRIES=1000
```

## Reloading Config
```python
from auto_workflow.config import reload_config
reload_config()
```
Caches are cleared (using lru_cache invalidation).
