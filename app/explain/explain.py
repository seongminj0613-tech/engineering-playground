from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .rules import SIGNAL_LABELS, THRESH, NEXT_STEP_RECIPES, RISK_RECIPES


def _sorted_signals(signals: Dict[str, float]) -> List[Tuple[str, float]]:
    items = [(k, float(v)) for k, v in (signals or {}).items() if v is not None]
    return sorted(items, key=lambda x: x[1], reverse=True)


def _pick_top_bottom(signals: Dict[str, float], topn: int = 2, bottomn: int = 2):
    s = _sorted_signals(signals)
    top = s[:topn]
    bottom = list(reversed(s[-bottomn:])) if len(s) >= bottomn else list(reversed(s))
    return top, bottom


def _fmt_pct(x: float) -> str:
    # 0~1 -> 0~100
    try:
        return f"{int(round(x * 100))}%"
    except Exception:
        return "?"


def generate_explanations(
    idea: Dict[str, Any],
    signals: Dict[str, float],
    score_components: Dict[str, float] | None = None,
    external_evidence_items: List[Dict[str, Any]] | None = None,
    max_bullets: int = 5,
) -> Dict[str, Any]:
    idea = idea or {}
    title = (idea.get("title") or "").strip()
    summary = (idea.get("summary") or "").strip()

    score_components = score_components or {}
    external_evidence_items = external_evidence_items or []

    top, bottom = _pick_top_bottom(signals, topn=2, bottomn=2)

    bullets: List[str] = []
    next_steps: List[str] = []
    risks: List[str] = []

    # 1) 강점 근거(Top drivers)
    for k, v in top:
        label = SIGNAL_LABELS.get(k, k)
        if v >= THRESH["ok"]:
            bullets.append(f"{label}이(가) 높음({_fmt_pct(v)}): {title or '이 아이디어'}에서 해당 요소가 비교적 명확하게 드러남")

    # 2) 감점/약점 근거(Top penalties)
    for k, v in bottom:
        label = SIGNAL_LABELS.get(k, k)
        if v <= THRESH["ok"]:
            bullets.append(f"{label}이(가) 낮음({_fmt_pct(v)}): 점수 방어를 위해 보완 포인트가 필요")

    # 3) 스코어 컴포넌트 기반 설명(설득력 강화)
    # positive/risk/volume/novelty 중 존재하는 것만
    if score_components:
        parts = []
        for key in ["positive", "risk", "volume", "novelty"]:
            if key in score_components and score_components[key] is not None:
                parts.append(f"{key}={score_components[key]:.2f}")
        if parts:
            bullets.append("점수 구성: " + ", ".join(parts))

    # 4) external evidence 인용형 근거(최대 2개)
    for ev in external_evidence_items[:2]:
        t = (ev.get("title") or "").strip()
        src = (ev.get("source") or "").strip()
        if t:
            bullets.append(f"외부 근거 연결: {t}" + (f" ({src})" if src else ""))

    # 5) next_steps: 하위 signals 기반 처방
    # 약한 것부터 우선
    bottom_sorted = sorted(_sorted_signals(signals), key=lambda x: x[1])  # low first
    for k, v in bottom_sorted:
        if v <= THRESH["ok"] and k in NEXT_STEP_RECIPES:
            # 아이디어별 차이를 위해 title/summary를 스텝 문장에 살짝 반영(단, 과도한 반복은 피함)
            recipe = NEXT_STEP_RECIPES[k]
            for step in recipe[:2]:  # 신호당 2개만
                if title:
                    next_steps.append(f"[{SIGNAL_LABELS.get(k, k)}] {step} — 대상: {title}")
                else:
                    next_steps.append(f"[{SIGNAL_LABELS.get(k, k)}] {step}")
        if len(next_steps) >= 5:
            break

    # 6) risks: 약한 signals 기반 + 외부근거 none이면 '검증 부족' 리스크 강화
    for k, v in bottom_sorted:
        if v <= THRESH["ok"] and k in RISK_RECIPES:
            risks.append(f"{RISK_RECIPES[k]} ({SIGNAL_LABELS.get(k, k)} {_fmt_pct(v)})")
        if len(risks) >= 4:
            break

    if not external_evidence_items and (signals.get("evidence", 1.0) <= THRESH["ok"]):
        risks.append("외부 근거가 연결되지 않아 신뢰도/설득 단계에서 약점이 될 수 있음")

    # 7) 중복 제거 + 길이 제한
    def _dedup(xs: List[str]) -> List[str]:
        seen = set()
        out = []
        for x in xs:
            x2 = " ".join(x.split())
            if x2 and x2 not in seen:
                out.append(x2)
                seen.add(x2)
        return out

    bullets = _dedup(bullets)[:max_bullets]
    next_steps = _dedup(next_steps)[:6]
    risks = _dedup(risks)[:5]

    # summary가 너무 비어있으면 bullets 첫줄이 반복될 수 있으니 보정(선택)
    if not summary and bullets:
        bullets[0] = bullets[0].replace("해당 요소가 비교적 명확하게 드러남", "회의 텍스트에서 상대적으로 명확하게 드러남")

    return {
        "evidence_bullets": bullets,
        "next_steps": next_steps,
        "risks": risks,
    }