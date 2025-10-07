"""Task abstraction and decorator."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Dict
import inspect
import asyncio
import functools
import time

from .types import TaskFn
from .utils import maybe_await, default_cache_key
from .exceptions import RetryExhaustedError, TimeoutError
from .build import current_build_context
from .events import emit
from .tracing import get_tracer

@dataclass(slots=True)
class TaskDefinition:
    name: str
    fn: TaskFn
    original_fn: TaskFn | None = None
    retries: int = 0
    retry_backoff: float = 0.0
    retry_jitter: float = 0.0
    timeout: Optional[float] = None
    cache_ttl: Optional[int] = None
    cache_key_fn: Callable[..., str] = default_cache_key
    tags: set[str] = field(default_factory=set)
    run_in: str = "async"  # one of: async, thread, process
    persist: bool = False   # store large result via artifact store (future)
    priority: int = 0  # higher runs earlier when ready

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        attempt = 0
        start_time = time.time()
        while True:
            try:
                async def _invoke():
                    if self.run_in == "async":
                        return await maybe_await(self.fn(*args, **kwargs))
                    if self.run_in == "thread":
                        return await asyncio.to_thread(self.fn, *args, **kwargs)
                    if self.run_in == "process":
                        from .executors.process_executor import get_process_pool
                        loop = asyncio.get_running_loop()
                        pool = get_process_pool()
                        import cloudpickle
                        from .executors.process_executor import run_pickled
                        fn_bytes = cloudpickle.dumps((self.fn, args, kwargs))
                        return await loop.run_in_executor(pool, functools.partial(run_pickled, fn_bytes))
                    raise RuntimeError(f"Unknown run_in mode: {self.run_in}")
                if self.timeout:
                    try:
                        return await asyncio.wait_for(_invoke(), timeout=self.timeout)
                    except asyncio.TimeoutError as te:
                        err: Exception = TimeoutError(self.name, te)
                    else:
                        continue  # pragma: no cover
                else:
                    try:
                        return await _invoke()
                    except Exception as e:  # noqa: BLE001
                        err = e
                # Reaching here means we have an exception in err
                e = err
                if isinstance(e, TimeoutError):
                    # treat like any retry-able error
                    pass
                if attempt < self.retries:
                    attempt += 1
                    emit("task_retry", {"task": self.name, "attempt": attempt, "max": self.retries})
                    sleep_dur = self.retry_backoff * (2 ** (attempt - 1))
                    if self.retry_jitter:
                        import random
                        sleep_dur += random.uniform(0, self.retry_jitter)
                    await asyncio.sleep(sleep_dur)
                    continue
                # wrap final failure
                if isinstance(e, TimeoutError):
                    raise e
                raise RetryExhaustedError(self.name, e) from e
            except Exception as e:  # noqa: BLE001 pragma: no cover
                if attempt < self.retries:
                    attempt += 1
                    emit("task_retry", {"task": self.name, "attempt": attempt, "max": self.retries})
                    sleep_dur = self.retry_backoff * (2 ** (attempt - 1))
                    if self.retry_jitter:
                        import random
                        sleep_dur += random.uniform(0, self.retry_jitter)
                    await asyncio.sleep(sleep_dur)
                    continue
                raise RetryExhaustedError(self.name, e) from e

    def cache_key(self, *args: Any, **kwargs: Any) -> str:
        return self.cache_key_fn(self.fn, args, kwargs)


    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # building vs immediate execution
        ctx = current_build_context()
        if ctx is None:
            # immediate execution outside a flow build (synchronous helper)
            tracer = get_tracer()
            async def _run():
                async with tracer.span(f"task:{self.name}"):
                    val = await self.run(*args, **kwargs)
                    if self.persist:
                        from .artifacts import get_store
                        store = get_store()
                        ref = store.put(val)
                        return ref
                    return val
            return asyncio.run(_run())
        return ctx.register(self.name, self.fn, args, kwargs, self)


def task(_fn: Optional[TaskFn] = None, *, name: Optional[str] = None, retries: int = 0,
         retry_backoff: float = 0.0, retry_jitter: float = 0.0, timeout: Optional[float] = None,
         cache_ttl: Optional[int] = None, cache_key_fn: Callable[..., str] = default_cache_key,
         tags: Optional[set[str]] = None, run_in: str = "async", persist: bool = False, priority: int = 0) -> Callable[[TaskFn], TaskDefinition]:
    """Decorator to define a task."""
    def wrap(fn: TaskFn) -> TaskDefinition:
        td_obj = TaskDefinition(
            name=name or fn.__name__,
            fn=fn,
            original_fn=fn,
            retries=retries,
            retry_backoff=retry_backoff,
            retry_jitter=retry_jitter,
            timeout=timeout,
            cache_ttl=cache_ttl,
            cache_key_fn=cache_key_fn,
            tags=tags or set(),
            run_in=run_in,
            persist=persist,
            priority=priority,
        )
        # original_fn already stored; no update_wrapper to avoid attribute errors with slots
        return td_obj

    if _fn is not None:
        return wrap(_fn)
    return wrap
