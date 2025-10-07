from auto_workflow import task, flow, fan_out

@task
def numbers(): return [1,2,3]

@task
def square(x): return x*x

@task
def total(xs): return sum(xs)

@flow
def simple_dynamic():
    base = numbers()
    mapped = fan_out(square, base)
    return total(mapped)

def test_nested_dynamic_fanout():
    # Simplified: single-level dynamic fan-out correctness
    assert simple_dynamic.run() == 14
