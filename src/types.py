"""Shared types for the checker (Stages 1-4).

These live here, not inside src/checker/, because more than one stage touches
them: Stage 3 emits Violations, Stage 4 aggregates them, Stage 5 compares them
against human labels, and both arms serialise the results.

GUARDRAIL: this module imports NO LLM code (no src.llm_client, no model calls).
Stage 3 verdicts are pure graph/set/index logic.
"""
from dataclasses import dataclass
from enum import Enum


class ViolationType(str, Enum):
    """The five violation types from the spec.

    Subclassing `(str, Enum)` makes each member an actual string: it compares
    equal to its value, json.dumps() serialises it without a custom encoder, and
    it still gives the closed set of an Enum. That matters because Stage 5
    computes precision/recall per type, where a typo'd bare string would become
    a phantom category that never matches a human label.
    """

    ORDER_INVERSION = "order_inversion"
    PRECONDITION_OMISSION = "precondition_omission"
    MANDATORY_STEP_DROP = "mandatory_step_drop"
    BRANCH_ERROR = "branch_error"
    FABRICATION = "fabrication"


# Which of G's conditions hold for this instance, keyed by the condition string
# copied verbatim from a step's `condition` field. A missing key means the guard
# does not hold (see `holds()` in the spec), so callers may pass a partial dict.
Scenario = dict[str, bool]


@dataclass(frozen=True)
class Violation:
    """One detected problem. Spec data contract: {type, offenders}.

    `offenders` is a tuple so the value is hashable (Violations can go in a set
    when deduping) and cannot be mutated in place despite frozen=True. For the
    two-step violations the spec's order is [precondition, step]: offenders[0]
    is the step that should have come first.
    """

    type: ViolationType
    offenders: tuple[str, ...]

    def to_dict(self) -> dict:
        return {"type": self.type.value, "offenders": list(self.offenders)}


@dataclass(frozen=True)
class CheckResult:
    """Per-answer verdict. Spec data contract: {valid, violations, first_fail}.

    `valid` is a property rather than a field because the spec derives it
    (`valid = len(violations) == 0`); storing it too would let the two disagree.

    `first_fail` is None when no offender appears in the answer itself - pure
    omissions have nothing to localise, since the spec filters offenders through
    the answer's position index before taking the earliest.
    """

    violations: tuple[Violation, ...] = ()
    first_fail: str | None = None

    @property
    def valid(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "violations": [v.to_dict() for v in self.violations],
            "first_fail": self.first_fail,
        }
