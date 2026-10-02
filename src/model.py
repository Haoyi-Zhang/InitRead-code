"""Owned, bounded heap model. This is not a JVM or a bytecode verifier.

A record is (ready, value, next), with Boolean ready/value and next=-1 or an
allocated object index. The policy is ready and (next is null or value<=next.value).
"""
from __future__ import annotations
from typing import Iterable

Heap = tuple[tuple[int, int, int], ...]
Location = tuple[int, int]
MAX_OBJECTS = 128

def validate(heap: Heap, roots: Iterable[int]) -> None:
    if not isinstance(heap, tuple) or not 1 <= len(heap) <= MAX_OBJECTS:
        raise ValueError("heap must contain 1..128 fixed allocated objects")
    for row in heap:
        if not isinstance(row, tuple) or len(row) != 3:
            raise ValueError("an object has exactly three fields")
        if any(type(x) is not int for x in row):
            raise ValueError("integer fields required; booleans are not identifiers")
        if row[0] not in (0, 1) or row[1] not in (0, 1) or not -1 <= row[2] < len(heap):
            raise ValueError("field outside the finite domain")
    if any(type(x) is not int or not 0 <= x < len(heap) for x in roots):
        raise ValueError("root outside allocated heap")

def reachable(heap: Heap, roots: Iterable[int]) -> set[int]:
    seen: set[int] = set()
    pending = list(roots)
    while pending:
        obj = pending.pop()
        if obj in seen:
            continue
        seen.add(obj)
        target = heap[obj][2]
        if target >= 0:
            pending.append(target)
    return seen

def evaluate(heap: Heap, obj: int) -> tuple[bool, tuple[tuple[int, int, int], ...]]:
    """Short-circuit evaluation and the complete, ordered read transcript."""
    reads: list[tuple[int, int, int]] = []
    def read(o: int, f: int) -> int:
        value = heap[o][f]
        reads.append((o, f, value))
        return value
    if read(obj, 0) == 0:
        return False, tuple(reads)
    target = read(obj, 2)
    if target == -1:
        return True, tuple(reads)
    return read(obj, 1) <= read(target, 1), tuple(reads)

def successor(heap: Heap, roots: frozenset[int], event: tuple[int, int, int, int]) -> tuple[Heap, frozenset[int]]:
    """An atomic candidate write with optional root addition; -1 means no addition.

Ready writes are trusted abstract metadata events, NOT proof that a Java
constructor ran. The checker never authenticates an external event source.
"""
    if not isinstance(event, tuple) or len(event) != 4 or any(type(v) is not int for v in event):
        raise ValueError("event must be an integer 4-tuple")
    obj, field, value, add = event
    if not (0 <= obj < len(heap) and 0 <= field < 3 and -1 <= add < len(heap)):
        raise ValueError("invalid event location or root")
    rows = list(heap)
    row = list(rows[obj]); row[field] = value; rows[obj] = tuple(row)
    newheap = tuple(rows)
    newroots = roots | ({add} if add >= 0 else set())
    validate(newheap, newroots)
    return newheap, frozenset(newroots)
