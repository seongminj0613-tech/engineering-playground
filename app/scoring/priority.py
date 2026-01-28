import math
from typing import List

def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))

def compute_raw_priority(
    feasibility: float,
    evidence: float,
    momentum: float,
    novelty: float,
    confidence: float,
) -> float:
    f = clamp(feasibility)
    e = clamp(evidence)
    m = clamp(momentum)
    n = clamp(novelty)
    c = clamp(confidence)

    base = (0.50 * f + 0.20 * m + 0.15 * e + 0.10 * n + 0.05 * c)

    raw = base * (0.6 + 0.4 * c)

    if e < 0.2:
        raw *= 0.7

    return clamp(raw)

def percentile_ranks(values: List[float]) -> List[float]:
    n = len(values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n

    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1

    if n == 1:
        return [1.0]
    return [r / (n - 1) for r in ranks]

def apply_priority_normalization(raw_priorities: List[float]) -> List[float]:
    return percentile_ranks(raw_priorities)