# app/scoring/model_v0_1.py
from typing import List, Dict


class ScoreModelV01:
    VERSION = "v0.1"

    def __init__(self, config=None):
        self.config = config or {}

    def total_score(self, idea: dict, signals: List[Dict]) -> dict:
        def s_type(s: dict) -> str:
            return (s.get("type") or "unknown").lower()

        def s_weight(s: dict) -> float:
            v = s.get("value", 0.0)
            try:
                return float(v)
            except Exception:
                return 0.0

        def s_source(s: dict) -> str:
            return str(s.get("source") or "unknown")

        pos = 0.0
        risk = 0.0

        for s in signals:
            t = s_type(s)
            w = s_weight(s)
            if "risk" in t or "negative" in t:
                risk -= abs(w)
            else:
                pos += max(0.0, w)

        signal_count = len(signals)
        source_count = len({s_source(s) for s in signals})

        volume = min(0.2, 0.02 * signal_count)
        novelty = min(0.2, 0.05 * max(0, source_count - 1))

        raw = pos + risk + volume + novelty
        total = max(0.0, min(1.0, raw))

        return {
            "total": round(total, 4),
            "components": {
                "positive": round(pos, 4),
                "risk": round(risk, 4),
                "volume": round(volume, 4),
                "novelty": round(novelty, 4),
            },
            "stats": {
                "signal_count": signal_count,
                "source_count": source_count,
            },
        }