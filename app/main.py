from __future__ import annotations
import json
from pathlib import Path
import csv
from pathlib import Path


from app.presentation.idea_card import IdeaCard, EvidenceItem
from app.presentation.export import export_cards_json
from app.scoring.priority import compute_raw_priority, apply_priority_normalization
from app.ingestion.hn_fetch import main as hn_fetch_main
from app.presentation.plot_daily import main as plot_daily_main
from app.presentation.plot_graph import main as plot_graph_main

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
    hn_fetch.py를 실행하고,
    결과가 return되지 않으면 저장된 CSV에서 다시 로드한다.
    """
    result = hn_fetch_main()

    # 1) hn_fetch_main이 리스트를 반환하면 그걸 사용
    if result is not None:
        return result

    # 2) 반환이 None이면 CSV에서 로드
    csv_path = Path("hn_meeting_summary_cases.csv")
    if not csv_path.exists():
        raise RuntimeError(
            "hn_fetch_main()이 None을 반환했고 "
            "hn_meeting_summary_cases.csv 파일도 없습니다."
        )

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"[main] loaded {len(rows)} rows from CSV fallback")
    return rows




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