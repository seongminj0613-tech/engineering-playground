from __future__ import annotations
from .score_utils import pick_total_score, _to_float

KEYWORD_BOOST = {
    "ai": 0.06, "llm": 0.06, "agent": 0.05, "rag": 0.05,
    "security": 0.06, "vulnerability": 0.05, "zero trust": 0.05,
    "cloud": 0.04, "aws": 0.05, "kubernetes": 0.06, "k8s": 0.06,
    "gpu": 0.05, "nvidia": 0.05, "inference": 0.04, "data": 0.03,
}

def compute_signal_boost(r: dict) -> tuple[float, dict]:
    title = (r.get("title") or "").lower()
    tags = r.get("tags") or []
    if not isinstance(tags, list):
        tags = [tags]
    tag_text = " ".join(str(t).lower() for t in tags)

    blob = f"{title} {tag_text}"
    score = 0.0
    top_reasons = []

    for k, w in KEYWORD_BOOST.items():
        if k in blob:
            score += w
            top_reasons.append((k, w))

    top_reasons = sorted(top_reasons, key=lambda x: x[1], reverse=True)[:2]
    breakdown = {
        f"signal:{k}": {"contribution": w, "why": f"keyword match: {k}"}
        for k, w in top_reasons
    }
    return min(score, 0.15), breakdown

def enrich_score_with_boosts(r: dict) -> dict:
    base = pick_total_score(r)
    signal, bd = compute_signal_boost(r)

    final = base + signal
    # ⚠️ 여기 캡(0~1 vs 0~100) 너 설정대로 유지
    cap = 1.0 if base <= 1.0 else 100.0
    final = max(0.0, min(cap, final))

    scores = r.get("scores", {}) if isinstance(r.get("scores", {}), dict) else {}
    scores["total"] = final
    scores.setdefault("breakdown", {})
    scores["breakdown"].update({
        "base": {"contribution": base, "why": "model/base total score"},
        **bd
    })

    r["total_score"] = final
    r["scores"] = scores
    return r