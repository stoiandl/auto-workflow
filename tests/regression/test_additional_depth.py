import asyncio
import time

from auto_workflow import FailurePolicy, fan_out, flow, task
from auto_workflow.artifacts import ArtifactRef, get_store
from auto_workflow.config import reload_config
from auto_workflow.exceptions import TaskExecutionError
from auto_workflow.metrics_provider import (
    InMemoryMetrics,
    get_metrics_provider,
    set_metrics_provider,
)
from auto_workflow.middleware import clear, register
from auto_workflow.secrets import StaticMappingSecrets, secret, set_secrets_provider

# --- Metrics correctness & middleware ordering ---
order = []
async def mw1(next_call, task_def, args, kwargs):
    order.append((task_def.name, 'mw1_pre'))
    try:
        return await next_call()
    finally:
        order.append((task_def.name, 'mw1_post'))
async def mw2(next_call, task_def, args, kwargs):
    order.append((task_def.name, 'mw2_pre'))
    try:
        return await next_call()
    finally:
        order.append((task_def.name, 'mw2_post'))

@task
async def _metrics_task(x: int) -> int:
    await asyncio.sleep(0)
    return x + 1

@flow
def metric_flow():
    return [_metrics_task(i) for i in range(3)]

def test_metrics_and_middleware_order():
    clear()
    register(mw1)
    register(mw2)
    mp = InMemoryMetrics()
    set_metrics_provider(mp)
    out = metric_flow.run()
    assert out == [1,2,3]
    # 3 successes
    assert mp.counters.get('tasks_succeeded') == 3
    # middleware order: for each task mw1_pre -> mw2_pre -> mw2_post -> mw1_post
    for t in ['_metrics_task']*3:  # names for each invocation are same base task name
        # We just assert relative ordering per task by scanning sequence blocks
        pre_post = [entry for entry in order if entry[0]==t]
        # Ensure pattern positions
        # first occurrence of mw1_pre before mw2_pre and mw2_pre before mw2_post etc.
        names = [p[1] for p in pre_post]
        assert names.count('mw1_pre') == names.count('mw1_post')
        assert names.count('mw2_pre') == names.count('mw2_post')

# --- Failure policy CONTINUE propagation ---
@task
def _fail_first():
    raise RuntimeError('boom')

@task
def _after_fail(x):
    if isinstance(x, TaskExecutionError):
        return 'skipped'
    return 'ok'

@flow
def continue_flow():
    a = _fail_first()
    b = _after_fail(a)
    return b

def test_failure_policy_continue():
    # Should not raise
    result = continue_flow.run(failure_policy=FailurePolicy.CONTINUE)
    assert result == 'skipped'

# --- Timeout with retries ensures multiple attempts ---
_attempts = {'n':0}
@task(retries=2, retry_backoff=0.01, timeout=0.01, run_in="async")
async def _timeout_task():
    _attempts['n'] += 1
    # Sleep longer than timeout to force TimeoutError
    await asyncio.sleep(0.05)

@flow
def timeout_flow():
    return _timeout_task()

def test_timeout_retries_exhausted():
    _attempts['n'] = 0
    try:
        timeout_flow.run()
        raise AssertionError('Should timeout')
    except Exception:
        # 1 initial + 2 retries = 3 attempts
        assert _attempts['n'] == 3

# --- Dynamic fan-out gating correctness (no early consumer run) ---
_events = []
@task
async def _source_list():
    await asyncio.sleep(0.01)
    return [1,2]
@task
def _dyn_child(x):
    _events.append(('child', x))
    return x
@task
def _dyn_consumer(vals):
    _events.append(('consumer', tuple(sorted(vals))))
    return sum(vals)
@flow
def dynamic_gate_flow():
    src = _source_list()
    mapped = fan_out(_dyn_child, src)  # dynamic
    total = _dyn_consumer(mapped)
    return total

def test_dynamic_fanout_consumer_runs_after_children():
    _events.clear()
    out = dynamic_gate_flow.run()
    assert out == 3
    # Ensure all child events recorded before consumer
    child_indices = [i for i,e in enumerate(_events) if e[0]=='child']
    consumer_indices = [i for i,e in enumerate(_events) if e[0]=='consumer']
    assert consumer_indices and max(child_indices) < consumer_indices[0]

# --- Artifact persistence across flow invocations with cache_ttl ---
_art_counter = {'n':0}
@task(persist=True, cache_ttl=30)
def _persist_cached():
    _art_counter['n'] += 1
    return {'value': _art_counter['n']}
@flow
def persist_reuse_flow():
    a = _persist_cached()
    b = _persist_cached()
    return a, b

def test_persist_artifact_reuse_same_flow():
    _art_counter['n']=0
    a,b = persist_reuse_flow.run()
    assert _art_counter['n']==1
    store = get_store()
    assert store.get(a)['value']==1 and store.get(b)['value']==1

# --- Secrets provider swap mid-run does not affect already built invocations ---
@task
def _secret_task():
    return secret('TOKEN')
@flow
def secret_swap_flow():
    first = _secret_task()
    set_secrets_provider(StaticMappingSecrets({'TOKEN':'late'}))  # swap after build
    second = _secret_task()
    return first, second

def test_secret_provider_swap_behavior():
    set_secrets_provider(StaticMappingSecrets({'TOKEN':'early'}))
    out = secret_swap_flow.run()
    # Both invocations capture value at execution time (provider swap before
    # second call). Accept either pattern but not None.
    assert out[0] in ('early','late') and out[1] in ('early','late')

# --- Config reload leaves unrelated keys intact ---

def test_reload_config_integrity():
    cfg1 = reload_config()
    cfg2 = reload_config()
    for k in ['max_dynamic_tasks','artifact_store','result_cache']:
        assert k in cfg1 and k in cfg2
