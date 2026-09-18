"""Stage 4: aggregate per-answer results into per-method / per-system rates.

Stage 3 judges one answer; this module counts. Still pure arithmetic - no LLM,
no graph logic, no re-checking. It consumes CheckResults and nothing else, so it
works unchanged for Arm 1 (questions) and Arm 2 (system answers).

Two different denominators matter, and conflating them is the easy mistake:
  - violation COUNT: how many violations of a type were emitted in total; one
    answer can contribute several.
  - answer RATE: the share of answers carrying at least one violation of a type.
Report rates for "how often does this system go wrong", counts for "how much".
"""
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from src.types import CheckResult, ViolationType


@dataclass(frozen=True)
class Aggregate:
    """Summary over a set of answers."""

    n: int
    n_valid: int
    violation_counts: Mapping[str, int]      # type -> total violations emitted
    answers_with_violation: Mapping[str, int]  # type -> answers carrying >=1
    n_localised: int  # answers whose first_fail is not None

    @property
    def valid_rate(self) -> float:
        return self.n_valid / self.n if self.n else 0.0

    def rate(self, violation_type: ViolationType | str) -> float:
        """Share of answers carrying at least one violation of this type."""
        key = getattr(violation_type, "value", violation_type)
        return self.answers_with_violation.get(key, 0) / self.n if self.n else 0.0

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "n_valid": self.n_valid,
            "valid_rate": self.valid_rate,
            "violation_counts": dict(self.violation_counts),
            "answers_with_violation": dict(self.answers_with_violation),
            "violation_rates": {t.value: self.rate(t) for t in ViolationType},
            "n_localised": self.n_localised,
        }


def aggregate(results: Iterable[CheckResult]) -> Aggregate:
    """Summarise one group of answers (one method, one system, or all of them)."""
    results = list(results)
    counts: Counter[str] = Counter()
    answers: Counter[str] = Counter()
    for r in results:
        types = [v.type.value for v in r.violations]
        counts.update(types)
        answers.update(set(types))  # set(): one answer counts once per type
    return Aggregate(
        n=len(results),
        n_valid=sum(1 for r in results if r.valid),
        violation_counts=dict(counts),
        answers_with_violation=dict(answers),
        n_localised=sum(1 for r in results if r.first_fail is not None),
    )


def aggregate_by(groups: Mapping[str, Iterable[CheckResult]]) -> dict[str, Aggregate]:
    """Per-method / per-system breakdown: {group name: Aggregate}.

    The caller decides what a group is - the checker never learns which system
    produced an answer, which keeps Stage 3 independent of the thing under test.
    """
    return {name: aggregate(rs) for name, rs in groups.items()}


def first_fail_positions(results: Iterable[CheckResult], answers: Iterable[list[str]]) -> list[int]:
    """Where in each answer the first failure landed, for localisation analysis.

    Answers with no localised failure are skipped rather than zero-filled: a
    valid answer has no position, and zero would pull a mean toward "fails
    immediately".
    """
    out = []
    for r, answer in zip(results, answers, strict=True):
        if r.first_fail is not None and r.first_fail in answer:
            out.append(answer.index(r.first_fail))
    return out
