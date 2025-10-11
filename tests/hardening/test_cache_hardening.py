import os
from pathlib import Path

from auto_workflow.cache import FileSystemResultCache, InMemoryResultCache


def test_filesystem_cache_hashing_and_sharding(tmp_path):
    c = FileSystemResultCache(tmp_path)
    long_key = "x" * 300
    c.set(long_key, {"v": 1})
    # Ensure file exists under hashed/sharded path
    # Since _path is private, we assert that some file exists below two levels
    shards = list(tmp_path.iterdir())
    assert shards, "no shard directories created"
    sub = list(shards[0].iterdir())
    assert sub, "no second-level shard directory"
    files = list(sub[0].iterdir())
    assert files and files[0].is_file()


def test_inmemory_cache_lru_bound(monkeypatch):
    from auto_workflow.config import load_config, reload_config

    monkeypatch.setenv("AUTO_WORKFLOW_RESULT_CACHE_MAX_ENTRIES", "5")
    reload_config()
    c = InMemoryResultCache()
    for i in range(10):
        c.set(f"k{i}", i)
    # bound should evict down to 5 entries
    assert len(c._store) <= 5
    # access one key to update LRU order and insert another to evict oldest
    list(c._store.keys())  # force OrderedDict iteration; not strictly needed
    c.get("k9", ttl=9999)
    c.set("new", 1)
    assert len(c._store) <= 5
