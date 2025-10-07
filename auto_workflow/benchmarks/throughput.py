import time

from auto_workflow import flow, task


@task
def noop(i: int) -> int:
    return i


@flow
def many(n: int = 1000):
    tasks = [noop(i) for i in range(n)]
    return tasks


def run_benchmark(n: int = 1000, repeat: int = 3):
    times = []
    for _ in range(repeat):
        start = time.time()
        many.run()
        times.append(time.time() - start)
    return {
        "tasks": n,
        "runs": repeat,
        "avg_s": sum(times) / len(times),
        "min_s": min(times),
        "max_s": max(times),
    }
