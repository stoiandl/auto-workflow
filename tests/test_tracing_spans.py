from auto_workflow import task, flow
from auto_workflow.tracing import set_tracer, get_tracer

class RecordingTracer:
    def __init__(self):
        self.spans = []
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def span(self, name: str, **attrs):
        entry = {'name': name, 'attrs': attrs}
        self.spans.append(entry)
        yield entry

rec = RecordingTracer()
set_tracer(rec)

@task
def a(): return 1

@task
def b(x): return x+1

@flow
def trace_flow():
    x = a(); y = b(x); return y

def test_tracing_spans_collected():
    assert trace_flow.run() == 2
    names = [s['name'] for s in rec.spans]
    # Flow span may not be recorded by dummy tracer; ensure task spans exist
    assert any(n.startswith('task:a') for n in names)
    assert any(n.startswith('task:b') for n in names)
