from __future__ import annotations

import hashlib
from datetime import date
from typing import Dict


WEIGHTS = {
    "novelty": 0.14,
    "specificity": 0.16,
    "feasibility": 0.18,
    "market_pull": 0.16,
    "evidence": 0.14,
    "clarity": 0.10,
    "trend_boost": 0.06,
    "freshness": 0.06,
}

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def score_from_signals(signals: Dict[str, float]) -> float:
    # signals are expected 0~1
    s = 0.0
    for k, w in WEIGHTS.items():
        s += float(signals.get(k, 0.0)) * w

    # 0~1 -> 0~100
    return _clamp(s * 100.0, 0.0, 100.0)

def seeded_jitter(idea_id: str, today: date, *, max_points: float = 0.8) -> float:
    """
    아주 미세한 변동(재현 가능):
    같은 idea_id라도 날짜가 바뀌면 jitter도 바뀜.
    """
    seed = f"{idea_id}|{today.isoformat()}".encode("utf-8")
    h = hashlib.sha256(seed).hexdigest()
    # 0~1
    u = int(h[:8], 16) / 0xFFFFFFFF
    # -1~1
    v = (u * 2.0) - 1.0
    return v * max_points