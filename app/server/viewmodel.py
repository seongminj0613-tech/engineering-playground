from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from app.runs.meeting_run import run_meeting_analysis_from_text
from app.explain.explain import generate_explanations

# ====== (1) UI 계약(스키마) ======

@dataclass
class Risk:
    type: str         # "data" | "tech" | "ops" | "legal" ...
    level: str        # "LOW" | "MED" | "HIGH"
    note: str

@dataclass
class IdeaCard:
    rank: int
    idea_id: str
    title: str
    summary: str
    feasibility_label: str     # "OK" | "CONDITIONAL" | "HARD"
    one_liner: str             # Explain Headline
    total_score_100: float
    signals: Dict[str, float]
    evidence_bullets: List[str]
    next_steps: List[str]
    risks: List[Risk]

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))

def score_to_100(x: float) -> float:
    x = float(x or 0.0)
    if 0.0 <= x <= 1.0:
        return round(x * 100.0, 2)
    if 0.0 <= x <= 10.0:
        return round((x / 10.0) * 100.0, 2)
    return round(x, 2)

# ====== (2) Feasibility 판정 + Explain(룰 기반 MVP) ======
def feasibility_judge(signals: Dict[str, float], mode: str) -> str:
    f = float(signals.get("feasibility", 0.0))
    e = float(signals.get("evidence", 0.0))
    c = float(signals.get("clarity", 0.0))

    # mode에 따라 threshold만 살짝 바꾸자 (MVP)
    if mode == "conservative":
        ok_f, ok_e = 0.72, 0.18
        cond_f = 0.50
    elif mode == "aggressive":
        ok_f, ok_e = 0.62, 0.10
        cond_f = 0.40
    else:  # balanced
        ok_f, ok_e = 0.68, 0.14
        cond_f = 0.45

    if f >= ok_f and e >= ok_e and c >= 0.45:
        return "OK"
    if f >= cond_f:
        return "CONDITIONAL"
    return "HARD"

def explain_one_liner(label: str, signals: Dict[str, float]) -> str:
    f = float(signals.get("feasibility", 0.0))
    e = float(signals.get("evidence", 0.0))
    c = float(signals.get("clarity", 0.0))

    if label == "OK":
        return "기술/리소스 난이도가 낮고 근거가 있어, 단기간 PoC로 검증 가능한 아이디어"
    if label == "CONDITIONAL":
        if e < 0.12:
            return "가능성은 있으나 근거가 부족해, 데이터/검증 확보가 선행조건"
        if c < 0.45:
            return "가능성은 있으나 요구사항이 불명확해, 스펙 정리가 선행조건"
        return "조건부로 추진 가능하며, 선행 리스크를 정리하면 실행 전환 가능"
    # HARD
    if f < 0.35:
        return "리소스/난이도 대비 효익이 불리해, 현 시점 즉시 추진은 어려움"
    return "리스크가 커서 우선순위 하향(추가 조사 후 재평가 권장)"

def default_evidence_bullets(label: str) -> List[str]:
    if label == "OK":
        return [
            "기술 구현 경로가 비교적 명확함(기존 스택/라이브러리 활용 가능)",
            "필요 리소스(인력/기간)가 작게 시작 가능(PoC 단위)",
            "운영/보안 리스크가 통제 가능한 수준"
        ]
    if label == "CONDITIONAL":
        return [
            "핵심 가설 검증을 위한 데이터/사용자 피드백이 필요",
            "요구사항/범위 정의가 선행되어야 일정 산정 가능",
            "리스크 항목(보안/정책/운영)을 체크리스트로 관리 필요"
        ]
    return [
        "필요 리소스 대비 기대효익이 불확실",
        "법/보안/운영 등 리스크가 크거나 통제 어려움",
        "아이디어 구체화/대안 검토 후 재평가 필요"
    ]

def default_next_steps(label: str) -> List[str]:
    if label == "OK":
        return [
            "PoC 범위(입력/출력/지표) 1페이지로 정의",
            "2주 타임박스 PoC 진행(담당자/마감일 확정)",
            "성공 기준(KPI/체크리스트) 설정 후 리뷰"
        ]
    if label == "CONDITIONAL":
        return [
            "선행조건(데이터/승인/리소스) 목록화 및 오너 지정",
            "요구사항/유저 시나리오를 3개로 축소해 명확화",
            "리스크(보안/운영) 사전검토 후 Go/No-Go"
        ]
    return [
        "문제정의/가치가설을 재정의(왜 해야 하는지 3문장)",
        "대안 솔루션 2~3개 비교(비용/리스크/효익)",
        "조건 충족 시 재평가 기준 수립"
    ]

def default_risks(label: str) -> List[Risk]:
    if label == "OK":
        return [Risk(type="ops", level="LOW", note="PoC 단위 운영 리스크 낮음")]
    if label == "CONDITIONAL":
        return [Risk(type="data", level="MED", note="데이터 확보/권한/품질이 변수")]
    return [Risk(type="tech", level="HIGH", note="구현 난이도 또는 리스크가 큼")]

def evidence_bullets_from_signals(label: str, signals: Dict[str, float], ev_titles: List[str]) -> List[str]:
    """
    1) 파이프라인 evidence 제목이 있으면 그걸 최우선(팩트 기반)
    2) 부족하면 signals를 근거로 부족한 부분을 설명(진짜 판단처럼 보이게)
    """
    bullets: List[str] = []

    # (1) 실제 evidence title 기반 (팩트)
    for t in ev_titles[:5]:
        bullets.append(f"외부 근거: {t}")

    # (2) 부족한 근거는 signals 기반으로 보강
    e = float(signals.get("evidence", 0.0))
    c = float(signals.get("clarity", 0.0))
    m = float(signals.get("market_pull", 0.0))
    f = float(signals.get("feasibility", 0.0))
    n = float(signals.get("novelty", 0.0))

    if e < 0.2:
        bullets.append("근거 점수가 낮음 → 시장/사용자/레퍼런스 자료를 추가 확보 필요")
    if c < 0.45:
        bullets.append("요구사항 명확도가 낮음 → 입력/출력/사용자 시나리오 정리가 필요")
    if m > 0.55:
        bullets.append("시장성 신호가 비교적 높음 → 타겟/페인포인트를 좁히면 설득력 상승")
    if f > 0.60:
        bullets.append("실행가능성 신호가 높음 → PoC로 빠르게 검증하기 유리")
    if n > 0.70:
        bullets.append("차별성 신호가 높음 → 기존 솔루션 대비 차이를 3포인트로 명문화 권장")

    # 너무 길어지면 컷
    return bullets[:6] if bullets else default_evidence_bullets(label)


def next_steps_from_signals(label: str, signals: Dict[str, float]) -> List[str]:
    e = float(signals.get("evidence", 0.0))
    c = float(signals.get("clarity", 0.0))
    m = float(signals.get("market_pull", 0.0))
    f = float(signals.get("feasibility", 0.0))

    steps: List[str] = []

    # evidence가 약하면: 조사/검증이 1순위
    if e < 0.25:
        steps.append("유사 서비스/시장 데이터 5개 수집 후 '왜 지금?' 근거 정리")
        steps.append("가설 1개를 정하고 검증 질문 5개로 사용자 인터뷰 설계")

    # clarity가 약하면: 스펙/범위 정리
    if c < 0.45:
        steps.append("입력/출력/성공기준(KPI) 1페이지로 정의")
        steps.append("유저 시나리오 3개로 축소(누가/언제/왜 쓰는지)")

    # feasibility가 약하면: 기술 PoC 우선
    if f < 0.45:
        steps.append("기술 PoC: 핵심 기능 1개만 2~3일 내 구현 가능성 확인")

    # market_pull이 높으면: MVP/테스트로 가기
    if m > 0.55 and f > 0.45:
        steps.append("2주 타임박스 MVP 제작 → 5명 사용자 테스트")

    # fallback
    if not steps:
        return default_next_steps(label)

    # 중복 제거 + 길이 제한
    uniq = []
    seen = set()
    for s in steps:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq[:5]


def risks_from_signals(label: str, signals: Dict[str, float]) -> List[Risk]:
    e = float(signals.get("evidence", 0.0))
    c = float(signals.get("clarity", 0.0))
    m = float(signals.get("market_pull", 0.0))
    f = float(signals.get("feasibility", 0.0))

    risks: List[Risk] = []

    if e < 0.2:
        risks.append(Risk(type="data", level="MED", note="근거/데이터 부족으로 판단 신뢰도가 낮음"))
    if c < 0.40:
        risks.append(Risk(type="ops", level="MED", note="요구사항 불명확 → 범위 확장/일정 리스크"))
    if f < 0.40:
        risks.append(Risk(type="tech", level="HIGH", note="구현 난이도/리소스 부담 가능성"))
    if m < 0.30:
        risks.append(Risk(type="biz", level="MED", note="수요 신호가 약함 → 타겟/가치제안 재정의 필요"))

    return risks[:3] if risks else default_risks(label)

# ====== (3) 네 기존 파이프라인 연결 포인트 ======
def _analyze_with_existing_pipeline(meeting_text: str, topn: int = 10, evidence_mode: str = "none") -> List[Dict[str, Any]]:
    report = run_meeting_analysis_from_text(
        meeting_text=meeting_text,
        meeting_id="uploaded",
        topn=topn,
        evidence_mode=evidence_mode,
    )
    rows = []
    for r in report["top"]:
        rows.append({
            "idea_id": r["idea_id"],
            "title": r["title"],
            "summary": r.get("summary") or r.get("reason") or "",
            "total_score": float(r.get("total_score", 0.0)),
            "signals": dict(r.get("signals") or {}),
            # 아래는 UI에서 더 쓰고 싶으면 viewmodel에 확장 가능
            "evidence": r.get("evidence") or [],
            "explain": r.get("explain") or "",
        })
    return rows

def build_viewmodel_from_meeting_text(
    meeting_text: str,
    meeting_name: str,
    topn: int,
    mode: str,
    evidence_mode: str = "none",
) -> Dict[str, Any]:

    rows = _analyze_with_existing_pipeline(meeting_text, topn=topn, evidence_mode=evidence_mode)
    rows = sorted(rows, key=lambda r: float(r.get("total_score", 0.0)), reverse=True)[:topn]

    cards: List[IdeaCard] = []

    for i, r in enumerate(rows, start=1):
        idea_id = str(r.get("idea_id", f"IDEA-{i:03d}"))
        title = str(r.get("title", ""))
        summary = str(r.get("summary", ""))

        signals = dict(r.get("signals") or {})

        # feasibility 판정
        label = feasibility_judge(signals, mode=mode)

        # explain (엔진 explain 우선)
        one_liner = (r.get("explain") or "").strip()
        if not one_liner:
            one_liner = explain_one_liner(label, signals)

        # score
        total_score = float(r.get("total_score", 0.0))
        total_100 = score_to_100(total_score)

        # evidence
        ev = r.get("evidence") or []
        evidence_bullets = []

        if isinstance(ev, list) and ev:
            for e in ev[:5]:
                if isinstance(e, dict):
                    t = (e.get("title") or "").strip()
                    if t:
                        evidence_bullets.append(t)

        if not evidence_bullets:
            evidence_bullets = evidence_bullets_from_signals(label, signals, evidence_bullets)
            
        ex = generate_explanations(
            idea=r,  # idea_dict 대신 r 써도 됨. r이 row dict니까
            signals=signals,
            score_components=r.get("score_components", {}),
            external_evidence_items=r.get("external_evidence_items", []),
        )

        # 기존 생성 결과를 ex가 있으면 덮어쓰기(또는 병합)
        evidence_bullets = ex.get("evidence_bullets") or evidence_bullets
        next_steps = ex.get("next_steps") or next_steps_from_signals(label, signals)
        risks = ex.get("risks") or risks_from_signals(label, signals)

        card = IdeaCard(
            rank=i,
            idea_id=idea_id,
            title=title,
            summary=summary,
            feasibility_label=label,
            one_liner=one_liner,
            total_score_100=total_100,
            signals={k: float(v) for k, v in signals.items()},
            evidence_bullets=evidence_bullets,
            next_steps=next_steps,
            risks=risks,
        )
        print("DEBUG", idea_id, title, "score", total_100, "signals", signals)

        cards.append(card)

    vm = {
        "meeting": {
            "title": meeting_name,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "summary": [
                "회의 내용을 업로드하면 아이디어를 추출하고",
                "상용 가능성 기준으로 Top10을 정렬합니다.",
                "각 아이디어는 근거/리스크/다음 액션까지 자동 제시됩니다."
            ],
            "idea_count": len(rows),
        },
        "selection": {"topn": topn, "mode": mode},
        "top": [
            {
                **asdict(c),
                "risks": c.risks,
            }
            for c in cards
        ],
    }

    return vm