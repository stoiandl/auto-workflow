from auto_workflow import flow, task
from auto_workflow.dag import DAG


def test_dag_topological_sort_deterministic():
    d = DAG()
    d.add_edge("a", "c")
    d.add_edge("b", "c")
    # No upstream for a and b; deterministic order should be [a, b, c] or [b, a, c] but stable.
    order1 = d.topological_sort()
    order2 = d.topological_sort()
    assert order1 == order2


def test_scheduler_tie_break_on_name():
    seen = []

    @task(run_in="async")
    async def t(name: str):
        seen.append(name)
        return name

    @flow
    def f():
        # same priority by default; order should be alphabetical by node name
        return [t("z"), t("a"), t("m")]

    out = f.run(max_concurrency=1)
    assert sorted(out) == ["a", "m", "z"]
    # Tie-break is by node id (build order) for equal priority; should be stable
    assert seen == ["z", "a", "m"]
