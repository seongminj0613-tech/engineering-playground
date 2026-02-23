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
            v = s.get("value", None)
            if v is None:
                v = s.get("score", None)
            if v is None:
                v = s.get("weight", 0.0)
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

        # 🔥 signals dict (type -> weight)
        sig = {s_type(s): s_weight(s) for s in signals}

        novelty_s = float(sig.get("novelty", 0.0))
        feas = float(sig.get("feasibility", 0.0))
        market = float(sig.get("market_pull", 0.0))
        clarity = float(sig.get("clarity", 0.0))
        evidence_cnt = float(sig.get("evidence_count", 0.0))

        # 🔥 가중 평균 방식 (0~1 스케일 유지)
        score = (
            novelty_s * 0.20 +
            feas      * 0.30 +
            market    * 0.25 +
            clarity   * 0.15 +
            min(evidence_cnt, 5.0) * 0.02
        )

        total = max(0.0, min(1.0, score))

        return {
            "total": round(total, 4),
            "components": {
                "novelty": round(novelty_s, 4),
                "feasibility": round(feas, 4),
                "market_pull": round(market, 4),
                "clarity": round(clarity, 4),
                "evidence_count": round(evidence_cnt, 4),
            },
            "stats": {
                "signal_count": len(signals),
                "source_count": len({s_source(s) for s in signals}),
            },
        }