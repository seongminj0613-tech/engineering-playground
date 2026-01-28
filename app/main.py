from __future__ import annotations
import json
from pathlib import Path
import importlib

from app.presentation.idea_card import IdeaCard, EvidenceItem
from app.presentation.export import export_cards_json
from app.scoring.priority import compute_raw_priority, apply_priority_normalization
REPORT_PATH = Path("data/reports/idea_cards.json")

def ensure_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    if isinstance(x, str):
        # "a,b,c" 형태도 안전 처리
        if "," in x:
            return [s.strip() for s in x.split(",") if s.strip()]
        return [x]
    return [str(x)]


def load_hn_results():
    """
    hn_fetch.py에서 '최종 결과 리스트'를 가져온다.
    ✅ 여기만 네 코드에 맞게 함수명/변수명 바꾸면 끝.
    """
    hn = importlib.import_module("hn_fetch")

    # 1) hn_fetch.py에 main()/run() 같은 엔트리가 있는 경우
    #    아래 중 맞는 걸 하나만 남기고 나머지는 지워도 됨.
    if hasattr(hn, "run_pipeline"):
        return hn.run_pipeline()
    if hasattr(hn, "main"):
        return hn.main()
    if hasattr(hn, "build_results"):
        return hn.build_results()

    # 2) 함수가 아니라, 이미 만들어진 리스트 변수가 있는 경우
    if hasattr(hn, "RESULTS"):
        return hn.RESULTS

    raise RuntimeError(
        "hn_fetch.py에서 결과를 가져올 수 없음. "
        "run_pipeline/main/build_results/RESULTS 중 하나를 찾지 못했음."
    )

def ensure_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    if isinstance(x, str):
        if "," in x:
            return [s.strip() for s in x.split(",") if s.strip()]
        return [x]
    return [str(x)]



def to_cards(raw_results):
    cards = []
    for i, r in enumerate(raw_results):
        # r이 dict라고 가정 (대부분 이렇게 되어있음)
        title = r.get("title") or r.get("idea") or f"idea_{i}"
        summary = r.get("summary") or r.get("one_liner") or title

        feasibility = float(r.get("feasibility", 0.0))
        confidence = float(r.get("confidence", 0.0))

        # evidence proxy (임시): mentions/points/comments 기반
        mentions = float(r.get("mentions", 0) or 0)
        points = float(r.get("total_points", r.get("points", 0)) or 0)
        comments = float(r.get("total_comments", r.get("comments", 0)) or 0)

        evidence = min(1.0, mentions / 10.0)
        momentum = min(1.0, (points + comments) / 200.0)
        novelty = float(r.get("novelty", 0.5))

        raw_priority = compute_raw_priority(
            feasibility=feasibility,
            evidence=evidence,
            momentum=momentum,
            novelty=novelty,
            confidence=confidence,
        )

        # decision_why -> drivers 변환 (있으면)
        drivers = []
        decision_why = r.get("decision_why", {})
        if isinstance(decision_why, dict):
            for k, v in decision_why.items():
                if isinstance(v, list):
                    drivers += [f"[{k}] {x}" for x in v]

        # evidence articles (있으면)
        evidence_items = []
        articles = r.get("articles") or r.get("evidence_articles") or []
        if isinstance(articles, list):
            for a in articles[:10]:
                if isinstance(a, dict):
                    evidence_items.append(EvidenceItem(
                        title=a.get("title", ""),
                        source=a.get("source", a.get("domain", "")),
                        published_at=a.get("published_at"),
                        url=a.get("url"),
                        snippet=a.get("snippet"),
                        relevance=float(a.get("relevance", 0.0) or 0.0),
                    ))

        card = IdeaCard(
            idea_id=str(r.get("id") or r.get("idea_id") or f"idea_{i}"),
            title=title,
            summary=summary,
            tags=r.get("keywords", r.get("tags", [])) or [],
            cluster_id=r.get("cluster_id"),
            scores={
                "feasibility": feasibility,
                "evidence": evidence,
                "momentum": momentum,
                "novelty": novelty,
                "confidence": confidence,
                "priority": raw_priority,        # 아직은 raw
                "raw_priority": raw_priority,    # 디버깅/표시용
            },
            drivers=drivers,               
            risks=ensure_list(r.get("risks")),
            evidence=evidence_items,
            trend=r.get("trend", {}),
            meta={
                "mentions": mentions,
                "points": points,
                "comments": comments,
            }
        )
        cards.append(card)

    cards.sort(key=lambda c: c.scores.priority, reverse=True)
    return cards


def main():
    raw = load_hn_results()
    cards = to_cards(raw)
    raw_ps = [c.scores.priority for c in cards]  # 현재는 raw_priority가 들어있음
    norm_ps = apply_priority_normalization(raw_ps)
    
    for c, p in zip(cards, norm_ps):
        c.scores.priority = p  # 최종 priority로 덮어쓰기
    out = export_cards_json(cards, str(REPORT_PATH))
    print(f"[OK] Exported {len(cards)} cards -> {out}")


if __name__ == "__main__":
    main()