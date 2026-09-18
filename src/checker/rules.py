"""Stage 3: the five rule checks, plus the per-answer verdict.

Pure graph/set/index logic - no LLM anywhere in this module (core guardrail).
Given the same answer, graph and scenario it always returns the same result.

Vocabulary, per the graph schema: `preconditions` ARE the order edges. One
relation, two failure modes - the precondition is absent (precondition_omission)
or present but later (order_inversion).
"""
from src.graph.schema import Graph
from src.types import CheckResult, Scenario, Violation, ViolationType


def holds(condition: str | None, scenario: Scenario) -> bool:
    """Does this step's guard apply? Unconditional steps always hold.

    An unknown condition string reads as False: a guard nobody asserted is not
    in force for this instance.
    """
    return condition is None or scenario.get(condition, False)


def check_mandatory_step_drop(answer: list[str], graph: Graph, scenario: Scenario) -> list[Violation]:
    """A mandatory step missing from the answer - but only where its guard holds.

    A step that is mandatory *only under a condition* is not required when that
    condition is false, so omitting it is not a violation.
    """
    present = set(answer)
    return [
        Violation(ViolationType.MANDATORY_STEP_DROP, (s.id,))
        for s in graph.steps.values()
        if s.mandatory and holds(s.condition, scenario) and s.id not in present
    ]


def check_precondition_edges(answer: list[str], graph: Graph) -> list[Violation]:
    """Both failure modes of a precondition edge, in one pass over the answer.

    Offender order is the spec's: (precondition, step) - offenders[0] is the
    step that should have come first. Steps not in G are skipped here; they are
    fabrications, and have no preconditions to check.
    """
    pos = {step_id: i for i, step_id in enumerate(answer)}
    present = set(answer)
    violations = []
    for step_id in answer:
        node = graph.steps.get(step_id)
        if node is None:
            continue
        for pre in node.preconditions:
            if pre not in present:
                violations.append(Violation(ViolationType.PRECONDITION_OMISSION, (pre, step_id)))
            elif pos[pre] > pos[step_id]:
                violations.append(Violation(ViolationType.ORDER_INVERSION, (pre, step_id)))
    return violations


def check_branch_error(answer: list[str], graph: Graph, scenario: Scenario) -> list[Violation]:
    """A guarded step that should be there and isn't, or is there and shouldn't be."""
    present = set(answer)
    violations = []
    for s in graph.steps.values():
        if s.condition is None:
            continue
        guard = holds(s.condition, scenario)
        if guard != (s.id in present):
            violations.append(Violation(ViolationType.BRANCH_ERROR, (s.id,)))
    return violations


def check_fabrication(answer: list[str], graph: Graph) -> list[Violation]:
    """A step the answer asserts that has no node in G.

    Trivial by design: the real judgment (is this entailed by the source text?)
    belongs to Stage 1 linking, which assigns a sentinel id to anything it
    cannot map. Here it simply surfaces as "id not in G".
    """
    return [
        Violation(ViolationType.FABRICATION, (step_id,))
        for step_id in answer
        if step_id not in graph.steps
    ]


def check(answer: list[str], graph: Graph, scenario: Scenario | None = None) -> CheckResult:
    """Run all five checks and localise the first failure.

    Overlap is deliberate and not deduped: a missing mandatory step that is also
    some step's precondition fires both mandatory_step_drop and
    precondition_omission, which keeps the per-type counts honest for Stage 5.
    """
    scenario = scenario or {}
    violations = [
        *check_mandatory_step_drop(answer, graph, scenario),
        *check_precondition_edges(answer, graph),
        *check_branch_error(answer, graph, scenario),
        *check_fabrication(answer, graph),
    ]
    # first_fail localises to a point in the ANSWER, so offenders that never
    # appear in it (pure omissions) cannot be the first failure.
    pos = {step_id: i for i, step_id in enumerate(answer)}
    offenders = [o for v in violations for o in v.offenders if o in pos]
    first_fail = min(offenders, key=pos.__getitem__) if offenders else None
    return CheckResult(tuple(violations), first_fail)
