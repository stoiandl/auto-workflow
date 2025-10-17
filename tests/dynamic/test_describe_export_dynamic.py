import re

from auto_workflow import fan_out, flow, task


@task
def numbers() -> list[int]:
    return [1, 2, 3]


@task
def square(x: int) -> int:
    return x * x


@task
def total(xs: list[int]) -> int:
    return sum(xs)


@flow
def simple_dynamic():
    ns = numbers()
    mapped = fan_out(square, ns)
    return total(mapped)


def test_describe_includes_dynamic_fanout_metadata():
    desc = simple_dynamic.describe()
    assert desc["flow"] == "simple_dynamic"
    # dynamic_fanouts list present with one entry
    dyn = desc.get("dynamic_fanouts")
    assert isinstance(dyn, list) and len(dyn) == 1
    entry = dyn[0]
    assert entry["type"] == "dynamic_fanout"
    assert entry["task"] == "square"
    # fanout id should be referenced by the consumer node's upstream
    fanout_id = entry["id"]
    nodes_by_id = {n["id"]: n for n in desc["nodes"]}
    # Find the consumer node (total:*) and ensure it depends on fanout node
    consumer = next(n for n in nodes_by_id.values() if n["task"] == "total")
    assert fanout_id in consumer["upstream"], consumer


@flow
def nested_dynamic():
    base = numbers()
    first = fan_out(square, base)
    second = fan_out(square, first)  # nested dynamic
    return total(second)


def test_describe_handles_nested_dynamic():
    desc = nested_dynamic.describe()
    assert desc["dynamic_count"] == 2
    # Two distinct fanout nodes should be present
    ids = {d["id"] for d in desc["dynamic_fanouts"]}
    assert len(ids) == 2


def test_export_dot_renders_fanout_nodes_and_edges():
    dot = simple_dynamic.export_dot()
    # Expect a fan_out node rendered with a diamond shape and edges source->fanout->consumer
    assert "fan_out(square)" in dot
    # source numbers:* to fanout:<id>
    assert re.search(r'"numbers:\d+" -> "fanout:\d+"', dot)
    # fanout:<id> to consumer total:*
    assert re.search(r'"fanout:\d+" -> "total:\d+"', dot)


@task
def as_list(xs: list[int]) -> list[int]:
    return list(xs)


@flow
def multi_consumer():
    base = numbers()
    mapped = fan_out(square, base)
    a = as_list(mapped)
    b = total(mapped)
    return a, b


def test_describe_multiple_consumers_reference_same_fanout():
    desc = multi_consumer.describe()
    dyn = desc["dynamic_fanouts"]
    assert len(dyn) == 1  # one fanout feeding two consumers
    fanout_id = dyn[0]["id"]
    # Both consumers should depend on the same fanout id
    consumers = [n for n in desc["nodes"] if n["task"] in ("as_list", "total")]
    assert len(consumers) == 2
    for c in consumers:
        assert fanout_id in c["upstream"], c


@task
def double(x: int) -> int:
    return x * 2


@task
def inc(x: int) -> int:
    return x + 1


@task
def concat(a: list[int], b: list[int]) -> list[int]:
    return list(a) + list(b)


@flow
def sibling_fanouts_and_merge():
    a = numbers()
    b = numbers()
    fa = fan_out(square, a)
    fb = fan_out(double, b)
    merged = concat(as_list(fa), as_list(fb))
    return total(merged)


def test_describe_sibling_fanouts_both_visible_and_wired():
    desc = sibling_fanouts_and_merge.describe()
    assert desc["dynamic_count"] == 2
    # The final consumer should depend on two distinct fanout ids
    final_node = next(n for n in desc["nodes"] if n["task"] == "total")
    # Collect all fanout ids
    fanout_ids = {d["id"] for d in desc["dynamic_fanouts"]}
    assert len([fid for fid in final_node["upstream"] if fid in fanout_ids]) == 2


@flow
def deep_nested_three_levels():
    base = numbers()
    f1 = fan_out(square, base)
    f2 = fan_out(double, f1)
    f3 = fan_out(inc, f2)
    return total(f3)


def test_describe_deep_nested_three_fanouts():
    desc = deep_nested_three_levels.describe()
    assert desc["dynamic_count"] == 3
    # Ensure there is a chain of fanout barrier dependencies in DOT
    dot = deep_nested_three_levels.export_dot()
    # Should render three diamond nodes
    assert dot.count('shape="diamond"') == 3


@flow
def shared_fanout_two_nested_mappers():
    base = numbers()
    f1 = fan_out(square, base)
    # Apply two different mappers on the same dynamic output
    d1 = fan_out(double, f1)
    d2 = fan_out(inc, f1)
    return total(concat(as_list(d1), as_list(d2)))


def test_describe_shared_source_multiple_nested_fanouts():
    desc = shared_fanout_two_nested_mappers.describe()
    # Expect 3 fanouts: f1 plus d1 and d2
    assert desc["dynamic_count"] == 3
    # There must be at least one parent->child fanout edge in DOT
    dot = shared_fanout_two_nested_mappers.export_dot()
    # Look for fanout:digit -> fanout:digit edges
    import re as _re

    assert _re.search(r'"fanout:\d+" -> "fanout:\d+"', dot)
