import json
import yaml
import datetime as dt
import re
import app.matching.match_external as _mx
from pathlib import Path
from collections import defaultdict
from app.scoring.model_v0_1 import ScoreModelV01
from app.reporting.render_md import render_md
from app.reporting.render_json import render_json
from app.signals.signals import build_signals_from_disclosure
from datetime import timezone, date
from app.scoring.signals import build_corpus_counter, extract_signals
from app.scoring.scorer import score_from_signals, seeded_jitter
from app.matching.match_external import load_external_docs, match_evidence_for_idea, compute_market_signal
from app.history.delta import apply_rank_and_delta, top_movers
from app.presentation.render_topn_html import main as render_topn_html_main

ROOT = Path(__file__).resolve().parents[1]



def norm_idea_id(x) -> str:
    """
    IDEA-001, IDEA_0000001, idea 1, IDEA1 등을 모두 'IDEA-<정수>'로 통일
    """
    if x is None:
        return ""
    s = str(x).strip().upper()
    # 숫자만 뽑기
    m = re.search(r"(\d+)", s)
    if not m:
        return s
    n = int(m.group(1))
    return f"IDEA-{n}"

def load_jsonl(path: Path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue  # ✅ 빈 줄 무시
            rows.append(json.loads(line))
    return rows

def load_config():
    cfg_path = ROOT / "configs" / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_run_id():
    return dt.datetime.now().strftime("run-%Y%m%d-%H%M%S")

def rank_scores(rows: list, top_k: int = 10) -> list:
    # 점수 키는 contract로 'total_score'가 최종이지만
    # 지금은 과도기라 score/total도 안전하게 커버
    def get_total(r: dict) -> float:
        return float(r.get("total_score", 0) or 0)
    ranked = sorted(rows, key=get_total, reverse=True)

    # rank 부여(옵션이지만 추천)
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i

    return ranked[:top_k]

def build_summary_from_idea(idea: dict) -> str:
    content = (idea.get("content") or "").strip()
    title = (idea.get("title") or "").strip()
    tags = idea.get("tags") or []

    if content:
        s = content.strip()
        if len(s) > 140:
            s = s[:140].rstrip() + "…"
        return s if s.endswith(".") else s + "."

    tag_hint = ", ".join(tags[:3]) if tags else "idea"
    return f"{title} 아이디어를 {tag_hint} 기반으로 실행 가능성 평가합니다."

def package_result(ideas: list, ranked_rows: list) -> dict:
    items = []

    ranked_by_id = { norm_idea_id(r.get("idea_id")): r for r in ranked_rows }

    for idea in ideas:
        iid = norm_idea_id(idea.get("idea_id"))
        r = ranked_by_id.get(iid)
        if not r:
            continue
        summary = build_summary_from_idea(idea)

        items.append({
            "idea": idea,
            "score": r,
            "rank": r.get("rank"),
            "summary": summary,
        })

    return {"status": "ok", "items": items}

def score_ideas(ideas: list, signals: list, scorer) -> list:
    scored_rows = []

    signals_by_idea = defaultdict(list)
    for s in signals:
        sid_raw = s.get("idea_id")
        sid = norm_idea_id(sid_raw)
        signals_by_idea[sid].append(s)

    print("DEBUG normalized signal keys:", list(signals_by_idea.keys()))

    for idea in ideas:
        iid_raw = idea.get("idea_id")
        iid = norm_idea_id(iid_raw)

        idea_signals = signals_by_idea.get(iid, [])
        if not idea_signals:
            continue

        res = scorer.total_score(idea, idea_signals)
        res["signal_count"] = len(idea_signals)
        res["idea_id"] = iid
        res["idea_id_raw"] = iid_raw
        scored_rows.append(res)

    print("DEBUG matched scored_rows:", len(scored_rows))
    return scored_rows

def render(result: dict) -> None:
    if result.get("status") == "error":
        print("❌ ERROR:", result.get("error", {}).get("message", "unknown"))
        return

    items = result.get("items", [])
    print(f"✅ ok: {len(items)} items")

    # --- 파일 출력은 여기서만 ---
    run_id = build_run_id()
    out_dir = ROOT / "reports" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # ✅ render_md가 기대하는 "ranked row" 형태로 변환
    ranked_rows = []
    for it in items:
        idea = it.get("idea", {}) or {}
        score = it.get("score", {}) or {}
       
        r = dict(score)
        r["signal_count"] = score.get("signal_count") or len(idea.get("signals", []) or idea.get("evidence", []) or [])
        r["evidence"] = score.get("evidence") or idea.get("evidence") or []
        if isinstance(r["evidence"], str):
            r["evidence"] = [r["evidence"]]
        
        r["rank"] = it.get("rank") or score.get("rank")
        r["title"] = idea.get("title") or idea.get("name") or idea.get("idea") or "(no title)"
       
        if "total_score" not in r:
            r["total_score"] = r.get("total") or r.get("score") or 0
            
        r["tags"] = idea.get("tags") or score.get("tags") or []
        if isinstance(r["tags"], str):
            r["tags"] = [r["tags"]]
        
        r["risk"] = score.get("risk") or idea.get("risk") or "unknown"
        r["market"] = idea.get("market") or score.get("market") or "unknown"
        r["feasibility"] = score.get("feasibility") or idea.get("feasibility") or "unknown"
        r["impact"] = score.get("impact") or idea.get("impact") or "unknown"
        r["confidence"] = score.get("confidence") or idea.get("confidence") or "unknown"

        ranked_rows.append(r)

    # 🔥 여기! for문 끝나고 정렬 1번만
    ranked_rows.sort(key=lambda r: int(r.get("rank") or 999999))
     

    context = {
        "date": dt.datetime.now().strftime("%Y-%m-%d"),
        "run_id": run_id,
        "rows": ranked_rows,      # 전체 점수 테이블
        "ranked": ranked_rows,    # 상위 리스트(지금은 same)
        "meta": {"n_items": len(items)},
        "movers_up": result.get("movers_up", []),
        "movers_down": result.get("movers_down", []),
    }

    render_json(out_dir, ranked_rows)
    render_md(out_dir, context)

    print(f"📁 Pipeline finished: {out_dir}")
    
def compute_freshness(idea: dict, today: date) -> float:
    raw = idea.get("created_at") or idea.get("date") or ""
    if not raw:
        return 0.3
    try:
        parsed = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        age_days = (today - parsed.date()).days
        if age_days <= 0: return 1.0
        if age_days <= 3: return 0.8
        if age_days <= 7: return 0.6
        if age_days <= 14: return 0.4
        return 0.2
    except Exception:
        return 0.3


def compute_trend_score(idea: dict, topic_freq: dict) -> float:
    tags = idea.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    if not tags:
        return 0.0
    freq = sum(topic_freq.get(t, 0) for t in tags)
    return min(1.0, freq / 10.0)


def score_ideas_v2_from_ideas_only(ideas: list) -> list:
    today = dt.datetime.now(timezone.utc).date()
    docs = load_external_docs(ROOT / "data" / "external" / "external_docs.jsonl")
    
 
    
    
    # novelty용 코퍼스
    corpus_counter = build_corpus_counter(ideas)

    # trend용 tag 빈도
    topic_freq = {}
    for it in ideas:
        tags = it.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        for t in tags:
            topic_freq[t] = topic_freq.get(t, 0) + 1

    scored_rows = []

    for it in ideas:
        iid_raw = it.get("idea_id") or it.get("id") or it.get("url") or it.get("title")
        
        iid_existing = it.get("idea_id")

        if iid_existing:
            iid = str(iid_existing)   # 기존 id 유지 (idea_22 그대로)
        else:
           iid = str(iid_raw) if iid_raw else f"idea_{len(scored_rows)+1}"
           it["idea_id"] = iid       # 없을 때만 생성

        freshness = compute_freshness(it, today)
        trend = compute_trend_score(it, topic_freq)
        # ✅ external evidence 매칭 (v1)
        evidence = match_evidence_for_idea(it, docs, top_n=3)
        it["external_evidence"] = evidence

        market_signal = compute_market_signal(evidence)
        # score_breakdown 형태로 남기고 싶으면(추천)
        sb = it.get("score_breakdown") or {}
        sb["novelty"] = it.get("novelty_score", 0)
        sb["feasibility"] = it.get("feasibility_score", 0)
        sb["trend"] = it.get("trend_score", 0)
        sb["risk"] = it.get("risk_score", 0)

        it["score_breakdown"] = sb
        

        signals = extract_signals(
            it,
            corpus_counter=corpus_counter,
            trend_score=trend,
            freshness=freshness,
        )

        base = score_from_signals(signals)
        jitter = seeded_jitter(iid or str(it.get("title", "")), today, max_points=0.8)
        w = 0.8  # 가중치 (너무 크면 외부근거가 다 먹어버림)
        total = max(0.0, min(100.0, base + jitter + (market_signal * w)))
        # ✅ idea에도 박아두기 (render에서 참고 가능)
        it["signals"] = signals
        it["total_score"] = round(total, 2)

        scored_rows.append({
            "idea_id": iid,
            "idea_id_raw": iid_raw,
            "total_score": round(total, 2),
            "signals": signals,
            "signal_count": len(signals),
            # render에서 쓰는 필드들 보강(선택)
            "evidence": it.get("evidence") or [],
            "market_signal": (it.get("score_breakdown") or {}).get("market_signal", 0.0),
            "tags": it.get("tags") or [],
            "risk": it.get("risk") or "unknown",
            "impact": it.get("impact") or "unknown",
            "confidence": it.get("confidence") or "unknown",
            "market": it.get("market") or "unknown",
            "feasibility": it.get("feasibility") or "unknown",            
        })

  
    
    return scored_rows


def main():
    print("🚀 Pipeline started")

    # 1) 설정 로드
    cfg = load_config()
    ideas = load_jsonl(ROOT / "data" / "raw" / "ideas.jsonl")
    
    from app.ingestion.external_docs import append_external_docs

    EXTERNAL_PATH = ROOT / "data" / "external" / "external_docs.jsonl"

    # ✅ 부트스트랩: 아이디어의 tags/title을 기반으로 "외부 문서 형태"를 만들어 일단 50개까지 채움
    # (진짜 외부 수집은 다음 단계에서 HN/RSS로 교체)
    bootstrap_docs = []
    for it in ideas:
        tags = it.get("tags") or []
        if isinstance(tags, str):
           tags = [tags]
        title = str(it.get("title") or it.get("idea") or "")
        if not title:
           continue
        bootstrap_docs.append({
            "source": "bootstrap",
            "title": f"Trend signal about: {title}",
            "url": f"https://example.local/{it.get('idea_id','')}",
            "snippet": str(it.get("content") or "")[:160],
            "tags": tags or ["trend"],
            "published_at": dt.datetime.now().date().isoformat(),
        })

    added = append_external_docs(EXTERNAL_PATH, bootstrap_docs)
    print("[EXTERNAL BOOTSTRAP] added:", added, "path:", EXTERNAL_PATH)
    
    if not ideas:
        result = {"status": "ok", "items": []}
        render(result)
        return

    scored_rows = score_ideas_v2_from_ideas_only(ideas)   # ✅ C: 여기서 signals+score 생성
  
   
    print("DEBUG ideas:", len(ideas), "scored_rows:", len(scored_rows))
    print("DEBUG idea_id sample:", ideas[0].get("idea_id") if ideas else None)
    print("DEBUG total_score sample:", scored_rows[0].get("total_score") if scored_rows else None)
    print("DEBUG signals sample keys:", list((scored_rows[0].get("signals") or {}).keys()) if scored_rows else None)
    
    ranked_top = rank_scores(scored_rows, top_k=50)
    today_str = dt.datetime.now().strftime("%Y-%m-%d")
    prev_str = (dt.datetime.now() - dt.timedelta(days=1)).strftime("%Y-%m-%d")

    prev_path = ROOT / "docs" / "history" / "data" / f"{prev_str}.json"
    prev_rows = []
    if prev_path.exists():
        try:
            prev_obj = json.loads(prev_path.read_text(encoding="utf-8"))
            # 네 스냅샷 포맷이 list면 그대로, dict면 items/rows 같은 키에서 꺼내기
            if isinstance(prev_obj, list):
                prev_rows = prev_obj
            elif isinstance(prev_obj, dict):
                prev_rows = prev_obj.get("rows") or prev_obj.get("ranked") or prev_obj.get("items") or []
        except Exception:
            prev_rows = []

    ranked_top = apply_rank_and_delta(ranked_top, prev_rows)

    up5, down5 = top_movers(ranked_top, k=5)
    print("\n=== MOVERS (UP 5) ===")
    for r in up5:
        print(r.get("idea_id"), "Δrank", r.get("rank_delta"), "Δscore", r.get("score_delta"))
    print("=== MOVERS (DOWN 5) ===")
    for r in down5:
        print(r.get("idea_id"), "Δrank", r.get("rank_delta"), "Δscore", r.get("score_delta"))
    print("=== END MOVERS ===\n")
     
    ranked_by_id = { norm_idea_id(r.get("idea_id")): r for r in ranked_top }

    for idea in ideas:
        iid = norm_idea_id(idea.get("idea_id"))
        r = ranked_by_id.get(iid)
        if not r:
            continue

        # summary (돈 안드는 룰 기반)
        idea["summary"] = idea.get("summary") or build_summary_from_idea(idea)

        # score/rank/delta도 같이 박아두면 render가 바로 씀
        idea["total_score"] = r.get("total_score", idea.get("total_score"))
        idea["rank"] = r.get("rank")
        idea["rank_delta"] = r.get("rank_delta")

        # evidence_count도 render에서 쓰면 좋음 (없으면 0)
        ev = idea.get("external_evidence") or idea.get("evidence") or []
        idea["evidence_count"] = len(ev) if isinstance(ev, list) else 0
    out_path = ROOT / "data" / "reports" / "idea_cards.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(ideas, f, ensure_ascii=False, indent=2)
    print(f"✅ idea_cards.json updated → {out_path}")
    
    result = package_result(ideas, ranked_top)
    result["movers_up"] = up5
    result["movers_down"] = down5
    render(result)
    
    render_topn_html_main()
    hist_dir = ROOT / "docs" / "history" / "data"
    hist_dir.mkdir(parents=True, exist_ok=True)
    today_path = hist_dir / f"{today_str}.json"
    today_path.write_text(json.dumps(ranked_top, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[HISTORY] saved:", today_path)
    
    render(result)
    
    return
   
if __name__ == "__main__":
    main()