import functools
import types

import pytest

from auto_workflow import utils


def test_is_coroutine_fn_with_partial():
    async def coro_fn():
        return 1

    partial_fn = functools.partial(coro_fn)
    assert utils.is_coroutine_fn(coro_fn) is True
    assert utils.is_coroutine_fn(partial_fn) is True


def test_default_cache_key_fallback(monkeypatch):
    def sample(a, b=2):
        return a + b

    # Force inspect.signature to raise to hit fallback branch
    def raising_signature(*args, **kwargs):  # noqa: ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr(utils.inspect, "signature", raising_signature)
    key = utils.default_cache_key(sample, (1,), {"b": 3})
    # Should still be a stable hex string of expected length
    assert isinstance(key, str) and len(key) == 64
