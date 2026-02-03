import json
import yaml
import datetime
import re
from pathlib import Path
from collections import defaultdict
from app.scoring.model_v0_1 import ScoreModelV01
from app.reporting.render_md import render_md
from app.reporting.render_json import render_json
from app.signals.signals import build_signals_from_disclosure


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
    return datetime.datetime.now().strftime("run-%Y%m%d-%H%M%S")

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

def package_result(ideas: list, ranked_rows: list) -> dict:
    items = []

    ranked_by_id = {
        r["idea_id"]: r for r in ranked_rows
    }

    for idea in ideas:
        iid = norm_idea_id(idea.get("idea_id"))
        r = ranked_by_id.get(iid)
        if not r:
            continue

        items.append({
            "idea": idea,
            "score": r,
            "rank": r.get("rank"),
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
        
        
        r["risk"] = (
            score.get("risk")
            or idea.get("risk")
            or "unknown"
        )
            
        r["market"] = idea.get("market") or score.get("market") or "unknown"
       
        r["feasibility"] = (
           score.get("feasibility")
           or idea.get("feasibility")
           or "unknown"
        ) 
        
        r["risk"] = score.get("risk") or idea.get("risk") or "unknown"
        r["impact"] = score.get("impact") or idea.get("impact") or "unknown"
        r["confidence"] = score.get("confidence") or idea.get("confidence") or "unknown"

        ranked_rows.append(r)

    context = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "run_id": run_id,
        "rows": ranked_rows,      # 전체 점수 테이블
        "ranked": ranked_rows,    # 상위 리스트(지금은 same)
        "meta": {"n_items": len(items)},
    }

    render_json(out_dir, ranked_rows)
    render_md(out_dir, context)

    print(f"📁 Pipeline finished: {out_dir}")

def main():
    print("🚀 Pipeline started")

    # 1) 설정 로드
    cfg = load_config()
    ideas = load_jsonl(ROOT / "data" / "raw" / "ideas.jsonl")
    signals = load_jsonl(ROOT / "data" / "raw" / "signals.jsonl")

    if not ideas or not signals:
        result = {"status": "ok", "items": []}  # 결과 0
        render(result)
        return

    scorer = ScoreModelV01(cfg.get("scoring", {}))
    scored_rows = score_ideas(ideas, signals, scorer)
    
    print("DEBUG ideas:", len(ideas), "signals:", len(signals))
    print("DEBUG idea_id sample:", ideas[0].get("idea_id") if ideas else None)
    print("DEBUG signal idea_id sample:", signals[0].get("idea_id") if signals else None)

    ranked_top = rank_scores(scored_rows, top_k=10)
    result = package_result(ideas, ranked_top)
    render(result)
    return
   
if __name__ == "__main__":
    main()