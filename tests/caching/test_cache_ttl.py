import time

from auto_workflow import flow, task


@task(cache_ttl=1)
def increment(x: int) -> int:
    return x + 1


@flow
def cache_flow():
    a = increment(1)
    b = increment(1)
    return [a, b]


def test_cache_ttl_expiry():
    first = cache_flow.run()
    assert first[0] == 2 and first[1] == 2
    # Wait for TTL to expire
    time.sleep(1.2)
    second = cache_flow.run()
    assert second[0] == 2 and second[1] == 2
