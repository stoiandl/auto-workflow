import time

from auto_workflow.cache import FileSystemResultCache, InMemoryResultCache


def test_filesystem_result_cache_roundtrip(tmp_path):
    cache = FileSystemResultCache(tmp_path)
    cache.set("k1", {"v": 1})
    assert cache.get("k1", ttl=10) == {"v": 1}


def test_inmemory_lru_eviction(monkeypatch):
    # Limit to 1 entry so insertion of second evicts first
    monkeypatch.setenv("AUTO_WORKFLOW_RESULT_CACHE_MAX_ENTRIES", "1")
    from auto_workflow.config import reload_config

    reload_config()
    cache = InMemoryResultCache()
    cache.set("a", 1)
    cache.set("b", 2)
    # Since max entries is 1, LRU eviction should have dropped 'a'
    assert cache.get("a", ttl=1000) is None
    assert cache.get("b", ttl=1000) == 2
