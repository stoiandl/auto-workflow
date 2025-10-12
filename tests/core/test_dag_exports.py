from auto_workflow.dag import DAG


def test_dag_to_dot_and_to_dict_and_subgraph():
    dag = DAG()
    dag.add_edge("a", "b")
    dag.add_edge("a", "c")
    dag.add_edge("b", "d")
    d = dag.to_dict()
    assert set(d.keys()) == {"a", "b", "c", "d"}
    dot = dag.to_dot()
    assert '"a" -> "b";' in dot and '"a" -> "c";' in dot

    sg = dag.subgraph(["a", "b", "d"])  # exclude c
    sd = sg.to_dict()
    assert set(sd.keys()) == {"a", "b", "d"}
    # ensure missing c doesn't break edges and no edge to c exists
    assert "c" not in sd
