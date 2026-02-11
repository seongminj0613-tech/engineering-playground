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
    idea id를 '형태만' 통일: 공백 제거 + 대문자.
    숫자 포맷(003 같은 leading zero)은 유지해서 snapshot 매칭 안정화.
    """
    if x is None:
        return ""
    return str(x).strip().upper()

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
def _to_float(x) -> float:
    try:
        if x is None:
            return 0.0
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if not s:
            return 0.0
        return float(s)
    except Exception:
        return 0.0


def build_breakdown_from_signals(signals: dict) -> dict:
    """
    signals(특성값)을 면접/포폴용 breakdown(설명 가능한 점수 항목)으로 변환.
    - 입력: novelty, specificity, feasibility, market_pull, evidence, clarity, trend_boost, freshness
    - 출력: 5개 breakdown 항목
    """
    s = {k: _to_float(v) for k, v in (signals or {}).items()}

    breakdown = {
        # 문제/설명 명확성
        "problem_clarity": 0.5 * s.get("specificity", 0.0) + 0.5 * s.get("clarity", 0.0),

        # 구현 가능성
        "feasibility": s.get("feasibility", 0.0),

        # 시장/트렌드 신호
        "market_signal": 0.5 * s.get("market_pull", 0.0)
                       + 0.3 * s.get("trend_boost", 0.0)
                       + 0.2 * s.get("freshness", 0.0),

        # 증거 강도
        "evidence_strength": s.get("evidence", 0.0),

        # 새로움/차별성
        "novelty": s.get("novelty", 0.0),
    }

    # 보기 좋게 라운딩(선택)
    breakdown = {k: round(v, 2) for k, v in breakdown.items()}
    return breakdown


def ensure_breakdown_and_total(row: dict) -> dict:
    """
    score_breakdown을 항상 '의미 있게' 채우고,
    total_score는 breakdown 합으로 강제.
    - breakdown이 없거나
    - breakdown이 전부 0이면
      => signals 기반으로 breakdown 재생성
    """
    signals = row.get("signals") or {}

    bd = row.get("score_breakdown") or {}
    if not isinstance(bd, dict):
        bd = {}

    # ✅ breakdown이 "사실상 비어있는지" 판정 (없거나 / 전부 0)
    def _is_empty_breakdown(d: dict) -> bool:
        if not d:
            return True
        vals = [v for v in d.values() if isinstance(v, (int, float))]
        if not vals:
            return True
        return all(float(v) == 0.0 for v in vals)

    # ✅ signals가 있으면, breakdown이 의미없을 때 강제 재생성
    if isinstance(signals, dict) and signals and _is_empty_breakdown(bd):
        bd = build_breakdown_from_signals(signals)

    # ✅ total_score는 breakdown 합으로 강제 (항상)
    total = round(sum(float(v) for v in bd.values() if isinstance(v, (int, float))), 2)

    row["score_breakdown"] = bd
    row["total_score"] = total

    # scores(dict)가 있으면 total 동기화(선택)
    if isinstance(row.get("scores"), dict):
        row["scores"]["total"] = total

    return row


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
            "doc_id": f"bootstrap_{it.get('idea_id','')}",
            "idea_id": it.get("idea_id",""),
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

    scored_rows = score_ideas_v2_from_ideas_only(ideas)

    # 🔥 signals → breakdown 강제 생성 + total 재계산
    def _to_float(x):
       try:
           return float(x)
       except:
           return 0.0

    for row in scored_rows:
        sig = row.get("signals") or {}

        # breakdown 새로 생성 (signals 기반)
        breakdown = {
            "novelty": _to_float(sig.get("novelty")),
            "feasibility": _to_float(sig.get("feasibility")),
            "trend": _to_float(sig.get("trend_boost")) + _to_float(sig.get("market_pull")),
            "risk": 0.0,  # 지금 risk signal 없으니까 0 유지
        }

        # total_score = breakdown 합 * 스케일
        total = sum(breakdown.values()) * 25   # 🔥 스케일링 (지금 total 40~50 맞추기)
        total = round(total, 2)

        row["score_breakdown"] = breakdown
        row["total_score"] = total

        if isinstance(row.get("scores"), dict):
           row["scores"]["total"] = total
      
    print("DEBUG ideas:", len(ideas), "scored_rows:", len(scored_rows))

    idea_map = { (i.get("idea_id") or ""): i for i in ideas }

    for r in scored_rows:
        iid = r.get("idea_id") or ""
        src = idea_map.get(iid, {})
        # evidence merge
        if "evidence" not in r or not r.get("evidence"):
            r["evidence"] = src.get("evidence", [])
        # evidence_count sync
        ev = r.get("evidence") or []
        if ev and not isinstance(ev, list):
            ev = [ev]
            r["evidence"] = ev
        r["evidence_count"] = len(ev) if isinstance(ev, list) else 0
  
   
    print("DEBUG ideas:", len(ideas), "scored_rows:", len(scored_rows))
    print("DEBUG idea_id sample:", ideas[0].get("idea_id") if ideas else None)
    print("DEBUG total_score sample:", scored_rows[0].get("total_score") if scored_rows else None)
    print("DEBUG signals sample keys:", list((scored_rows[0].get("signals") or {}).keys()) if scored_rows else None)
    
    ranked_top = rank_scores(scored_rows, top_k=50)
    ranked_top = rank_scores(scored_rows, top_k=50)

    today_str = dt.datetime.now().strftime("%Y-%m-%d")

    history_dir = ROOT / "docs" / "history" / "data"

    # 오늘 이전 가장 최신 snapshot 찾기
    cands = sorted(history_dir.glob("*.json"))
    cands = [p for p in cands if p.name != "index.json" and p.stem < today_str]

    prev_rows = []
    prev_path = cands[-1] if cands else None

    print("DEBUG prev_path:", prev_path, "exists:", (prev_path.exists() if prev_path else False))

    if prev_path and prev_path.exists():
        try:
            raw = prev_path.read_text(encoding="utf-8")
            prev_obj = json.loads(raw)

            if isinstance(prev_obj, list):
                prev_rows = prev_obj
            elif isinstance(prev_obj, dict):
                prev_rows = prev_obj.get("rows") or prev_obj.get("ranked") or prev_obj.get("items") or []
            else:
                prev_rows = []

        except Exception as e:
            print("❌ DEBUG prev load failed:", repr(e))
            prev_rows = []
    else:
        prev_rows = []

    print("DEBUG prev_rows_len:", len(prev_rows))

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
        idea["score_delta"] = r.get("score_delta")

        # evidence_count도 render에서 쓰면 좋음 (없으면 0)
        ev = idea.get("external_evidence") or idea.get("evidence") or []
        idea["evidence_count"] = len(ev) if isinstance(ev, list) else 0


    ext_map = {}
    try:
        EXTERNAL_PATH = ROOT / "data" / "external" / "external_docs.jsonl"
        if EXTERNAL_PATH.exists():
            for line in EXTERNAL_PATH.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue

                iid = (d.get("idea_id") or "").strip()
                if not iid:
                    continue

                ext_map.setdefault(iid, []).append(d)
    except Exception:
        ext_map = {}

    # ideas 리스트에 강제 attach
    for r in ideas:
        iid = (r.get("idea_id") or "").strip()

        ev = r.get("evidence") or []
        if ev and not isinstance(ev, list):
            ev = [ev]

        extra = ext_map.get(iid, [])

        if extra:
            seen = set()
            merged = []

            for x in (ev + extra):
                if isinstance(x, dict):
                       key = x.get("doc_id") or (x.get("title"), x.get("url"))
                else:
                    key = str(x)

                if key in seen:
                    continue
                seen.add(key)
                merged.append(x)

            r["evidence"] = merged
        else:
            r["evidence"] = ev

        r["evidence_count"] = len(r["evidence"]) if isinstance(r.get("evidence"), list) else 0
    out_path = ROOT / "data" / "reports" / "idea_cards.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    for row in ranked_top:
        bd = row.get("score_breakdown") or {}
        if isinstance(bd, dict) and bd:
            row["total_score"] = round(sum(float(v) for v in bd.values()), 2)
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(ranked_top, f, ensure_ascii=False, indent=2)
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
def apply_rank_and_delta(ranked_rows: list[dict], prev_rows: list[dict]) -> list[dict]:
    # 안전 total_score 추출 함수
    def get_total(x: dict) -> float:
        if x is None:
            return 0.0
        if x.get("total_score") is not None:
            try:
                return float(x.get("total_score") or 0.0)
            except:
                return 0.0
        s = x.get("scores")
        if isinstance(s, dict):
            try:
                return float(s.get("total") or 0.0)
            except:
                return 0.0
        return 0.0

    def get_rank(x: dict):
        if x is None:
            return None
        v = x.get("rank")
        return None if v is None else int(v)

    prev_by_id = { norm_idea_id(r.get("idea_id")): r for r in (prev_rows or []) }
    print("DEBUG prev_rows_len:", len(prev_rows))
    print("DEBUG prev_by_id_len:", len(prev_by_id))
    print("DEBUG prev_sample_keys:", (list(prev_rows[0].keys())[:10] if prev_rows else None))


    for r in ranked_rows:
        if r.get("rank") == 1:
            print("DEBUG cur_id:", r.get("idea_id"), "norm:", norm_idea_id(r.get("idea_id")), "prev_hit:", norm_idea_id(r.get("idea_id")) in prev_by_id)
        iid = norm_idea_id(r.get("idea_id"))
        p = prev_by_id.get(iid)

        prev_rank = get_rank(p)
        cur_rank = get_rank(r)

        # rank delta
        if prev_rank is None or cur_rank is None:
            r["rank_prev"] = None
            r["rank_delta"] = None
        else:
            r["rank_prev"] = prev_rank
            r["rank_delta"] = prev_rank - cur_rank

        # score delta
        if p is None:
            r["score_prev"] = None
            r["score_delta"] = None
        else:
            prev_score = get_total(p)
            cur_score = get_total(r)
            r["score_prev"] = prev_score
            r["score_delta"] = round(cur_score - prev_score, 4)

    return ranked_rows

if __name__ == "__main__":
    
    main()