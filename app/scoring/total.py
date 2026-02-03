from .sub_scores import (
    score_feasibility,
    score_market,
    score_trend,
)
from .risk import risk_penalty
from .weights import (
    WEIGHT_FEASIBILITY,
    WEIGHT_MARKET,
    WEIGHT_TREND,
)
from .utils import clamp


def compute_total_score(idea: dict) -> dict:
    f = score_feasibility(idea)
    m = score_market(idea)
    t = score_trend(idea)
    r = risk_penalty(idea)

    base = (
        f * WEIGHT_FEASIBILITY
        + m * WEIGHT_MARKET
        + t * WEIGHT_TREND
    )

    total = clamp(base - r)

    return {
        "id": idea.get("id"),
        "title": idea.get("title"),
        "feasibility": round(f, 2),
        "market": round(m, 2),
        "trend": round(t, 2),
        "risk_penalty": round(r, 2),
        "total_score": round(total, 2),
    }