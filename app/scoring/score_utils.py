from __future__ import annotations

def _to_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

def pick_total_score(r: dict) -> float:
    for k in ["total_score", "total", "final", "final_score", "score"]:
        if k in r:
            return _to_float(r.get(k))

    s = r.get("scores") or r.get("score") or {}
    if isinstance(s, dict):
        for k in ["total", "total_score", "final", "final_score", "score"]:
            if k in s:
                return _to_float(s.get(k))

        nums = [v for v in s.values() if isinstance(v, (int, float))]
        if nums:
            return float(max(nums))
    return 0.0