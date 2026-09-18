"""Ground-truth procedure graph schema (Stage 0).

A graph is a DAG of steps. `preconditions` are the order edges: s3 in s4's
preconditions means s3 must happen before s4. `condition` is a guard string;
a conditional step is required only when its guard holds, so `mandatory` on a
conditional step means "mandatory when the condition applies".
"""
import json
import re
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

GRAPHS_DIR = Path(__file__).resolve().parents[2] / "data" / "graphs"
# Document id as printed on the SOP itself, e.g. LSASDPROC-301-R7 or
# DOH-SCMS-WOM-SOP-01-A. The edition/revision of the source document goes in
# `scope_note`; the filename must start with this id.
SOP_ID = re.compile(r"^[A-Z][A-Z0-9-]*[A-Z0-9]$")


@dataclass(frozen=True)
class Step:
    id: str
    text: str
    mandatory: bool
    preconditions: tuple[str, ...]
    condition: str | None
    src: str


@dataclass(frozen=True)
class Graph:
    sop_id: str
    title: str
    scope_note: str
    steps: dict[str, Step]

    def order(self) -> tuple[str, ...]:
        """One valid topological order of step ids."""
        return tuple(TopologicalSorter({s.id: s.preconditions for s in self.steps.values()}).static_order())


def from_dict(d: dict) -> Graph:
    if not SOP_ID.match(d["sop_id"]):
        raise ValueError(f"sop_id must include revision, got {d['sop_id']!r}")
    steps: dict[str, Step] = {}
    for raw in d["steps"]:
        s = Step(raw["id"], raw["text"], bool(raw["mandatory"]), tuple(raw["preconditions"]),
                 raw["condition"], raw["src"])
        if s.id in steps:
            raise ValueError(f"duplicate step id {s.id}")
        steps[s.id] = s
    for s in steps.values():
        if unknown := set(s.preconditions) - steps.keys():
            raise ValueError(f"{s.id} has unknown preconditions {sorted(unknown)}")
    g = Graph(d["sop_id"], d["title"], d["scope_note"], steps)
    try:
        g.order()
    except CycleError as e:
        raise ValueError(f"precondition cycle: {e.args[1]}") from None
    return g


def load(path: str | Path) -> Graph:
    path = Path(path)
    g = from_dict(json.loads(path.read_text()))
    if not path.stem.startswith(g.sop_id):
        raise ValueError(f"{path.name}: filename must start with sop_id {g.sop_id}")
    return g


if __name__ == "__main__":  # validate every committed graph
    for p in sorted(GRAPHS_DIR.glob("*.json")):
        print(p.name, "OK", load(p).order())
