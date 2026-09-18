import pytest

from src.graph.schema import from_dict


def step(id, pre=()):
    return {"id": id, "text": "", "mandatory": True, "preconditions": list(pre), "condition": None, "src": ""}


def graph(steps, sop_id="LSASDPROC-301-R7"):
    return {"sop_id": sop_id, "title": "", "scope_note": "", "steps": steps}


def test_valid_graph_orders_preconditions_first():
    g = from_dict(graph([step("s2", ["s1"]), step("s1")]))
    assert g.order() == ("s1", "s2")


@pytest.mark.parametrize("bad", [
    graph([], sop_id="lsasdproc 301"),                 # not a document id
    graph([step("s1"), step("s1")]),                   # duplicate id
    graph([step("s1", ["s9"])]),                       # unknown precondition
    graph([step("a", ["b"]), step("b", ["a"])]),       # cycle
])
def test_rejects_broken_graphs(bad):
    with pytest.raises(ValueError):
        from_dict(bad)


def test_committed_graphs_follow_the_codebook():
    """Every graph loads, and every step is traceable (R8) and non-empty (R2)."""
    from src.graph.schema import GRAPHS_DIR, load

    graphs = [load(p) for p in sorted(GRAPHS_DIR.glob("*.json"))]
    assert graphs, "no graphs committed"
    for g in graphs:
        assert g.scope_note.strip(), f"{g.sop_id}: scope_note required"
        for s in g.steps.values():
            assert s.text.strip() and s.src.strip(), f"{g.sop_id}/{s.id}: text and src required"
            assert s.condition is None or s.condition.strip(), f"{g.sop_id}/{s.id}: empty condition"
