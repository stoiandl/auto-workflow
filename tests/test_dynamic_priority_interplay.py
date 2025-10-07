from auto_workflow import task, flow, fan_out

@task
def nums(): return [1,2,3]

@task(priority=5)
def square(x): return x*x

@task(priority=0)
def aggregate(xs): return sum(xs)

@flow
def dyn_priority_flow():
    values = nums()
    squares = fan_out(square, values)
    total = aggregate(squares)
    return total

def test_dynamic_priority_interplay():
    assert dyn_priority_flow.run() == 14
