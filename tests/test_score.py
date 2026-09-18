from src.checker.score import aggregate, aggregate_by, first_fail_positions
from src.types import CheckResult, Violation
from src.types import ViolationType as VT


def result(*pairs, first_fail=None):
    return CheckResult(tuple(Violation(t, tuple(o)) for t, o in pairs), first_fail)


def test_all_valid():
    a = aggregate([result(), result()])
    assert a.n == 2 and a.n_valid == 2 and a.valid_rate == 1.0
    assert a.rate(VT.ORDER_INVERSION) == 0.0


def test_counts_and_rates_use_different_denominators():
    """One answer with two inversions: count 2, but only 1 answer affected."""
    two_in_one = result((VT.ORDER_INVERSION, ("s1", "s2")), (VT.ORDER_INVERSION, ("s3", "s4")))
    a = aggregate([two_in_one, result()])
    assert a.violation_counts["order_inversion"] == 2
    assert a.answers_with_violation["order_inversion"] == 1
    assert a.rate(VT.ORDER_INVERSION) == 0.5
    assert a.valid_rate == 0.5


def test_rate_accepts_enum_or_string():
    a = aggregate([result((VT.BRANCH_ERROR, ("s5",)))])
    assert a.rate(VT.BRANCH_ERROR) == a.rate("branch_error") == 1.0


def test_empty_group_does_not_divide_by_zero():
    a = aggregate([])
    assert a.n == 0 and a.valid_rate == 0.0 and a.rate(VT.FABRICATION) == 0.0


def test_localisation_is_counted_separately_from_validity():
    omission = result((VT.MANDATORY_STEP_DROP, ("s2",)))  # nothing to localise
    inversion = result((VT.ORDER_INVERSION, ("s1", "s2")), first_fail="s2")
    a = aggregate([omission, inversion])
    assert a.n_valid == 0 and a.n_localised == 1


def test_aggregate_by_groups_independently():
    groups = aggregate_by({
        "rag_a": [result(), result()],
        "rag_b": [result((VT.FABRICATION, ("X",)), first_fail="X")],
    })
    assert groups["rag_a"].valid_rate == 1.0
    assert groups["rag_b"].valid_rate == 0.0
    assert groups["rag_b"].rate(VT.FABRICATION) == 1.0


def test_first_fail_positions_skips_unlocalised_answers():
    results = [
        result((VT.ORDER_INVERSION, ("s1", "s2")), first_fail="s2"),
        result((VT.MANDATORY_STEP_DROP, ("s9",))),  # no position
        result(),
    ]
    answers = [["s2", "s1", "s3"], ["s1", "s2"], ["s1", "s2", "s3"]]
    assert first_fail_positions(results, answers) == [0]


def test_to_dict_reports_every_type():
    d = aggregate([result((VT.BRANCH_ERROR, ("s5",)))]).to_dict()
    assert set(d["violation_rates"]) == {t.value for t in VT}
    assert d["violation_rates"]["branch_error"] == 1.0
    assert d["violation_rates"]["order_inversion"] == 0.0
