"""Partial bridge from owned Java trace records to the bounded heap model.

This module deliberately does not import the production checker, producer, or
reference oracle.  It validates only the trace record and returns either a
bounded abstract snapshot or UNKNOWN.  A mapped ``ready`` bit means that the
owned fixture's ``readObject`` callback exited; it is not constructor history,
JVM verification, or a claim that every external alias was observed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAX_OBJECTS = 128
BLOCKING_FEATURES = (
    "early_external_escape",
    "read_resolve_substitution",
    "missing_field",
    "type_shape_mismatch",
    "callback_observed_unready",
    "observer_coverage_gap",
    "failure_after_escape",
)


@dataclass(frozen=True)
class BridgeResult:
    status: str
    reason: str
    heap: tuple[tuple[int, int, int], ...] | None = None
    roots: frozenset[int] | None = None
    ready_meaning: str | None = None

    def as_json(self) -> dict[str, Any]:
        value: dict[str, Any] = {"status": self.status, "reason": self.reason}
        if self.heap is not None:
            value["heap"] = [list(row) for row in self.heap]
        if self.roots is not None:
            value["roots"] = sorted(self.roots)
        if self.ready_meaning is not None:
            value["ready_meaning"] = self.ready_meaning
        return value


def _unknown(reason: str) -> BridgeResult:
    return BridgeResult("UNKNOWN", reason)


def map_observation(observation: Any) -> BridgeResult:
    """Validate one observation and, only on the narrow owned discipline, map it.

    The bridge is fail-closed.  In particular, ``readResolve`` substitution,
    early publication, missing-field provenance, type-shape mismatch, callback
    reads of an unfinished peer, public-hook coverage gaps, and exceptional
    deserialization all return UNKNOWN rather than being coerced into the
    abstract model.
    """
    if type(observation) is not dict:
        return _unknown("observation is not an object")
    if type(observation.get("case")) is not str:
        return _unknown("case identifier is missing")
    if type(observation.get("success")) is not bool:
        return _unknown("success flag is not Boolean")
    if observation["success"] is not True:
        return _unknown("ObjectInputStream did not return a root")

    features = observation.get("features")
    if type(features) is not dict or set(features) != set(BLOCKING_FEATURES):
        return _unknown("feature vector is incomplete")
    for key in BLOCKING_FEATURES:
        if type(features[key]) is not bool:
            return _unknown(f"feature {key} is not Boolean")
        if features[key]:
            return _unknown(f"unsupported concrete feature: {key}")

    snapshot = observation.get("snapshot")
    if type(snapshot) is not dict or set(snapshot) != {"heap", "roots", "ready_provenance"}:
        return _unknown("exact final snapshot is unavailable")
    if snapshot["ready_provenance"] != "owned_readObject_callback_exit":
        return _unknown("ready provenance is not the owned callback-exit marker")

    rows = snapshot["heap"]
    roots_input = snapshot["roots"]
    if type(rows) not in (list, tuple) or not 1 <= len(rows) <= MAX_OBJECTS:
        return _unknown("heap size is outside 1..128")
    normalized: list[tuple[int, int, int]] = []
    for row in rows:
        if type(row) not in (list, tuple) or len(row) != 3:
            return _unknown("object record does not have three fields")
        if any(type(value) is not int for value in row):
            return _unknown("object field has a non-integer value")
        ready, value, target = row
        if ready not in (0, 1) or value not in (0, 1) or not -1 <= target < len(rows):
            return _unknown("object field is outside the bounded domain")
        normalized.append((ready, value, target))

    if type(roots_input) not in (list, tuple) or len(roots_input) > MAX_OBJECTS:
        return _unknown("root collection is not a bounded sequence")
    # Exact-type and range checks intentionally precede deduplication.  Python
    # considers 0 == False == 0.0, so set conversion must not happen first.
    for root in roots_input:
        if type(root) is not int or not 0 <= root < len(normalized):
            return _unknown("root is not an exact in-range integer")
    roots = frozenset(roots_input)
    if not roots:
        return _unknown("the concrete run returned no modeled root")

    return BridgeResult(
        "MAPPED",
        "owned final snapshot satisfies the narrow bridge discipline",
        tuple(normalized),
        roots,
        "owned readObject callback exit only; not constructor or JVM initialization history",
    )
