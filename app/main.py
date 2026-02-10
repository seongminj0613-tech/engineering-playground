from __future__ import annotations
from pathlib import Path
import csv
import json

from app.core.config import load_config
from app.core.logging import setup_logger
from app.core.run_summary import RunTimer

from app.presentation.idea_card import IdeaCard, EvidenceItem
from app.presentation.export import export_cards_json
from app.scoring.priority import compute_raw_priority, apply_priority_normalization
from app.ingestion.hn_fetch import main as hn_fetch_main
from app.presentation.plot_daily import main as plot_daily_main
from app.presentation.plot_graph import main as plot_graph_main
from app.presentation.plot_idea_rank import plot_idea_rank

from app.presentation.publish_run_latest import main as publish_run_latest_main

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




def add_part(breakdown, key, score, weight, why):
    breakdown[key] = {
        "score": round(float(score), 3),
        "weight": float(weight),
        "contribution": round(float(score) * float(weight), 3),
        "why": why,
    }

def _to_float(x, default=0.0):
    """숫자/문자열/None 등 어떤 값이 와도 안전하게 float로."""
    if x is None:
        return float(default)
    if isinstance(x, (int, float)):
        return float(x)
    # "0.12", " 1 ", 같은 문자열은 변환 가능
    if isinstance(x, str):
        s = x.strip()
        try:
            return float(s)
        except ValueError:
            return float(default)
    # dict 등 예상 못한 타입이면 default
    return float(default)
    



def to_cards(raw_results):
    cards = []
    for i, r in enumerate(raw_results):
        if not isinstance(r, dict):
            r = {"title": str(r), "summary": str(r)}
        title = r.get("title") or r.get("idea") or f"idea_{i}"
        summary = r.get("summary") or r.get("one_liner") or title

        feasibility = _to_float(r.get("feasibility", 0.0))
        confidence  = _to_float(r.get("confidence", 0.0))

        mentions  = _to_float(r.get("mentions", 0))
        points    = _to_float(r.get("total_points", r.get("points", 0)))
        comments  = _to_float(r.get("total_comments", r.get("comments", 0)))

        evidence = min(1.0, mentions / 10.0)
        momentum = min(1.0, (points + comments) / 200.0)
        novelty     = _to_float(r.get("novelty", 0.5))

        raw_priority = compute_raw_priority(
            feasibility=feasibility,
            evidence=evidence,
            momentum=momentum,
            novelty=novelty,
            confidence=confidence,
        )

        # decision_why -> drivers
        drivers = []
        decision_why = r.get("decision_why", {})
        if isinstance(decision_why, dict):
            for k, v in decision_why.items():
                if isinstance(v, list):
                    drivers += [f"[{k}] {x}" for x in v]

        # evidence articles
        evidence_items = []
        articles = r.get("articles") or r.get("evidence_articles") or []
        if isinstance(articles, list):
            for a in articles[:10]:
                if isinstance(a, dict):
                    evidence_items.append(
                        EvidenceItem(
                            title=a.get("title", ""),
                            source=a.get("source", a.get("domain", "")),
                            published_at=a.get("published_at"),
                            url=a.get("url"),
                            snippet=a.get("snippet"),
                            relevance=float(a.get("relevance", 0.0) or 0.0),
                        )
                    )

        # === B단계: breakdown 계산 ===
        breakdown = {}

        add_part(breakdown, "evidence", evidence, 0.35,
                 f"mentions={mentions}, points={points}, comments={comments}")

        add_part(breakdown, "momentum", momentum, 0.25,
                 "points + comments 기반 확산도")

        add_part(breakdown, "feasibility", feasibility, 0.25,
                 "입력된 구현 가능성 점수")

        add_part(breakdown, "novelty", novelty, 0.15,
                 "기본 novelty score")

        add_part(breakdown, "confidence", confidence, 0.00,
                 "현재 total에는 미반영")

        total_score = sum(v["contribution"] for v in breakdown.values())

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
                "priority": raw_priority,        # 아직 raw
                "raw_priority": raw_priority,    # 표시용
                "total": round(total_score, 3),  # ✅ 추가
                "breakdown": breakdown,          # ✅ 추가
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

    # ⚠️ scores가 dict면 이렇게 정렬해야 함
    cards.sort(key=lambda c: c.scores.priority, reverse=True)
    return cards

def main() -> int:
    cfg = load_config()
    logger = setup_logger(cfg.log_level, cfg.log_json)

    timer = RunTimer(cfg.run_dir)
    logger.info(f"run_start run_id={timer.summary.run_id} top_k={cfg.top_k}")

    try:
        raw = load_hn_results()
        timer.summary.ingested = len(raw)

        cards = to_cards(raw)
        timer.summary.ranked = len(cards)

        raw_ps = [c.scores.priority for c in cards]
        norm_ps = apply_priority_normalization(raw_ps)
        for c, p in zip(cards, norm_ps):
            c.scores.priority = p

        out = export_cards_json(cards, str(REPORT_PATH))
        timer.summary.rendered = True

        plot_idea_rank(cards)
        
        summary_path = timer.save()
        publish_run_latest_main()
        logger.info(f"run_done run_id={timer.summary.run_id} out={out} summary={summary_path.as_posix()}")
        return 0

    except Exception:
        timer.summary.errors += 1
        summary_path = timer.save()
        logger.exception(f"run_fail run_id={timer.summary.run_id} summary={summary_path.as_posix()}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())