from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence

@dataclass(frozen=True, order=True)
class Interval:
    lower: int
    upper: int
    def __post_init__(self):
        if self.lower > self.upper:
            raise ValueError("lower > upper")

def quorum_regions(intervals: Sequence[Interval], q: int):
    """Exact quorum-supported regions over integer picoseconds.

    Closed interval [L,U] contributes +1 at L and -1 at U+1.  Sweeping these
    integer event points produces exact contiguous regions where support >= q.
    """
    if q <= 0:
        raise ValueError("q must be positive")
    if not intervals or q > len(intervals):
        return []
    events={}
    for i in intervals:
        events[i.lower]=events.get(i.lower,0)+1
        events[i.upper+1]=events.get(i.upper+1,0)-1
    points=sorted(events)
    support=0
    open_start=None
    out=[]
    for idx,p in enumerate(points):
        support += events[p]
        next_p = points[idx+1] if idx+1 < len(points) else None
        if support >= q and open_start is None:
            open_start=p
        if support < q and open_start is not None:
            out.append(Interval(open_start,p-1))
            open_start=None
        # If this is the last event, support should have returned to zero.
        if next_p is None and open_start is not None:
            out.append(Interval(open_start,p-1))
            open_start=None
    return out

def consensus(intervals: Sequence[Interval], f: int):
    n = len(intervals)
    if f < 0:
        raise ValueError("f < 0")
    if n < 3*f + 1:
        raise ValueError("requires N >= 3f+1")
    q = 2*f + 1
    regions = quorum_regions(intervals, q)
    if len(regions) != 1:
        return {"verdict": "TIME_CONFLICT", "q": q, "regions": regions}
    return {"verdict": "CONSENSUS", "q": q, "interval": regions[0], "regions": regions}

def order(a: Interval, b: Interval):
    if a.upper < b.lower:
        return "A_BEFORE_B"
    if b.upper < a.lower:
        return "B_BEFORE_A"
    return "ORDER_INDETERMINATE"
