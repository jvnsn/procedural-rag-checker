"""Stage 3 tests on a hand-built graph.

Hand-built so that a failure localises to the rule logic, not to parsing or to a
real graph's quirks. Shape: s1 -> s2 -> s3 linear, s4 optional, s5 guarded by
"voc" and mandatory only when that guard holds.
"""
import pytest

from src.checker.rules import check
from src.graph.schema import from_dict
from src.types import ViolationType as VT


def step(id, pre=(), mandatory=True, condition=None):
    return {"id": id, "text": id, "mandatory": mandatory, "preconditions": list(pre),
            "condition": condition, "src": "test"}


@pytest.fixture
def g():
    return from_dict({
        "sop_id": "TEST-SOP-01", "title": "t", "scope_note": "hand-built",
        "steps": [
            step("s1"),
            step("s2", ["s1"]),
            step("s3", ["s2"]),
            step("s4", mandatory=False),
            step("s5", ["s3"], condition="voc"),
        ],
    })


def types(result):
    return [v.type for v in result.violations]


def test_valid_answer_has_no_violations(g):
    r = check(["s1", "s2", "s3"], g)
    assert r.valid and r.violations == () and r.first_fail is None


def test_optional_step_may_be_omitted_or_included(g):
    assert check(["s1", "s2", "s3"], g).valid
    assert check(["s1", "s2", "s3", "s4"], g).valid


def test_order_inversion_fires_on_a_swap(g):
    r = check(["s2", "s1", "s3"], g)
    assert types(r) == [VT.ORDER_INVERSION]
    assert r.violations[0].offenders == ("s1", "s2")  # (precondition, step)
    assert r.first_fail == "s2"  # earliest offender present in the answer


def test_dropped_mandatory_step_also_breaks_its_edge(g):
    """Overlap is intended: the spec reports both rather than deduping."""
    r = check(["s1", "s3"], g)
    assert sorted(types(r)) == sorted([VT.MANDATORY_STEP_DROP, VT.PRECONDITION_OMISSION])
    assert r.first_fail == "s3"  # s2 is absent, so only s3 can localise


def test_pure_omission_leaves_first_fail_null(g):
    r = check(["s1", "s2"], g)
    assert types(r) == [VT.MANDATORY_STEP_DROP]
    assert r.first_fail is None


def test_guarded_step_required_only_when_its_condition_holds(g):
    assert check(["s1", "s2", "s3"], g).valid  # guard false: omitting s5 is fine
    r = check(["s1", "s2", "s3"], g, {"voc": True})
    assert sorted(types(r)) == sorted([VT.MANDATORY_STEP_DROP, VT.BRANCH_ERROR])


def test_wrong_branch_taken_when_guard_is_false(g):
    r = check(["s1", "s2", "s3", "s5"], g)
    assert types(r) == [VT.BRANCH_ERROR]


def test_fabricated_step_is_reported_and_skipped_by_edge_checks(g):
    r = check(["s1", "s2", "s3", "UNMAPPED"], g)
    assert types(r) == [VT.FABRICATION]
    assert r.first_fail == "UNMAPPED"


def test_real_graph_accepts_its_own_topological_order():
    from src.graph.schema import GRAPHS_DIR, load

    graph = load(GRAPHS_DIR / "DOH-SCMS-WOM-SOP-01-A.json")
    scenario = {s.condition: True for s in graph.steps.values() if s.condition}
    assert check(list(graph.order()), graph, scenario).valid
