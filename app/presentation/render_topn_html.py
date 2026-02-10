from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime

# ✅ history는 snapshots.py로 전담
from app.history.snapshots import (
    _today_slug,
    load_prev_rank_map,
    write_history_snapshot_json,
    write_history_snapshot,
    write_history_index,
)

ROOT = Path(__file__).resolve().parents[2]  # app/ 기준 2단계 위
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"

# ✅ 너 프로젝트에서 "최신 결과" 파일명에 맞춰서 하나만 쓰면 됨
CANDIDATES = [
    DATA_DIR / "reports" / "idea_cards.json",
    DATA_DIR / "registry" / "ideas.jsonl",
    DATA_DIR / "raw" / "ideas.jsonl",
]


# =========================
# I/O helpers
# =========================
def _load_rows(path: Path) -> list[dict]:
    if path.suffix == ".json":
        obj = json.loads(path.read_text(encoding="utf-8"))

        # case A: list[dict]
        if isinstance(obj, list):
            return obj

        # case B: {"items":[...]} or {"ideas":[...]} or {"cards":[...]}
        if isinstance(obj, dict):
            for k in ["items", "ideas", "cards", "rows", "data"]:
                v = obj.get(k)
                if isinstance(v, list):
                    return v

        raise ValueError(f"JSON format not recognized: {path}")

    if path.suffix == ".jsonl":
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    if path.suffix == ".csv":
        import csv

        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    raise ValueError(f"Unsupported: {path}")


def _pick_latest_file() -> Path:
    for p in CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        "No input data found. Expected one of:\n" + "\n".join(str(p) for p in CANDIDATES)
    )


def _to_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _escape(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# =========================
# Scoring
# =========================
def pick_total_score(r: dict) -> float:
    # 1) top-level 우선
    for k in ["total_score", "total", "final", "final_score", "score"]:
        if k in r:
            return _to_float(r.get(k))

    # 2) nested(scores)도 지원
    s = r.get("scores") or r.get("score") or {}
    if isinstance(s, dict):
        for k in ["total", "total_score", "final", "final_score", "score"]:
            if k in s:
                return _to_float(s.get(k))

        nums = [v for v in s.values() if isinstance(v, (int, float))]
        if nums:
            return float(max(nums))

    return 0.0


KEYWORD_BOOST = {
    "ai": 0.06,
    "llm": 0.06,
    "agent": 0.05,
    "rag": 0.05,
    "security": 0.06,
    "vulnerability": 0.05,
    "zero trust": 0.05,
    "cloud": 0.04,
    "aws": 0.05,
    "kubernetes": 0.06,
    "k8s": 0.06,
    "gpu": 0.05,
    "nvidia": 0.05,
    "inference": 0.04,
    "data": 0.03,
}


def compute_signal_boost(r: dict) -> tuple[float, dict]:
    """title/tags에서 키워드 기반 가산점 + breakdown 생성"""
    title = (r.get("title") or "").lower()
    tags = r.get("tags") or []
    if not isinstance(tags, list):
        tags = [tags]
    tag_text = " ".join(str(t).lower() for t in tags)

    blob = f"{title} {tag_text}"
    score = 0.0
    reasons = []

    for k, w in KEYWORD_BOOST.items():
        if k in blob:
            score += w
            reasons.append((k, w))

    reasons = sorted(reasons, key=lambda x: x[1], reverse=True)[:2]
    breakdown = {
        f"signal:{k}": {"contribution": w, "why": f"keyword match: {k}"}
        for k, w in reasons
    }
    return min(score, 0.15), breakdown  # 과도한 폭주 방지


def enrich_score_with_boosts(r: dict) -> dict:
    """base + keyword boost -> final total_score, scores.breakdown 채움"""
    base = pick_total_score(r)
    signal, bd = compute_signal_boost(r)

    final = base + signal

    # 점수 스케일 clamp: base가 1 이하로 돌면 0~1, 아니면 0~100
    cap = 1.0 if base <= 1.0 else 100.0
    final = max(0.0, min(cap, final))

    scores = r.get("scores", {}) if isinstance(r.get("scores", {}), dict) else {}
    scores["total"] = final
    scores.setdefault("breakdown", {})
    scores["breakdown"].update(
        {
            "base": {"contribution": base, "why": "model/base total score"},
            **bd,
        }
    )

    r["total_score"] = final
    r["scores"] = scores
    return r


# =========================
# Render Top-N table rows
# =========================
def render_top_n(rows: list[dict], n: int = 15) -> list[dict]:
    enriched: list[dict] = []
    for r in rows:
        try:
            enriched.append(enrich_score_with_boosts(dict(r)))
        except Exception:
            enriched.append(dict(r))  # row 깨져도 계속

    ranked = sorted(enriched, key=pick_total_score, reverse=True)[:n]

    out: list[dict] = []
    for i, r in enumerate(ranked, start=1):
        total_score = pick_total_score(r)

        scores = r.get("scores", {}) if isinstance(r.get("scores", {}), dict) else {}
        scores.setdefault("total", total_score)

        evidence = r.get("evidence", [])
        if evidence and not isinstance(evidence, list):
            evidence = [evidence]

        tags = r.get("tags", [])
        if tags and not isinstance(tags, list):
            tags = [tags]

        out.append(
            {
                "rank": i,
                "idea_id": r.get("idea_id", ""),
                "title": r.get("title", "(untitled)"),
                "summary": r.get("summary", ""),
                "tags": tags,
                "trend": r.get("trend", ""),
                "total_score": total_score,
                "scores": scores,
                "score_breakdown": r.get("score_breakdown", {}),
                "evidence": evidence,
                "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
                "risks": r.get("risks", []),
                "assumptions": r.get("assumptions", []),
            }
        )
    return out


# =========================
# KPI + HTML
# =========================
def compute_kpis(table_rows: list[dict]) -> dict:
    total = len(table_rows)
    new_cnt = up_cnt = down_cnt = same_cnt = 0

    for r in table_rows:
        d = r.get("rank_delta", None)
        if d is None:
            new_cnt += 1
        elif d > 0:
            up_cnt += 1
        elif d < 0:
            down_cnt += 1
        else:
            same_cnt += 1

    scores = []
    for r in table_rows:
        s = r.get("scores", {})
        if isinstance(s, dict):
            scores.append(_to_float(s.get("total", r.get("total_score", 0.0))))
        else:
            scores.append(_to_float(r.get("total_score", 0.0)))

    if scores:
        mx = max(scores)
        mn = min(scores)
        avg = sum(scores) / len(scores)
    else:
        mx = mn = avg = 0.0

    return {
        "total": total,
        "new": new_cnt,
        "up": up_cnt,
        "down": down_cnt,
        "same": same_cnt,
        "score_max": mx,
        "score_min": mn,
        "score_avg": avg,
    }


def build_html(table_rows: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    kpi = compute_kpis(table_rows)

    # tag 집계
    tag_counts: dict[str, int] = {}
    for r in table_rows:
        tags = r.get("tags") or []
        if not isinstance(tags, list):
            tags = [tags]
        for t in tags:
            ts = str(t).strip()
            if not ts:
                continue
            tag_counts[ts] = tag_counts.get(ts, 0) + 1
    top_tags = sorted(tag_counts.items(), key=lambda kv: kv[1], reverse=True)[:24]

    # ideas json
    ideas_json = json.dumps(table_rows, ensure_ascii=False)
    ideas_json_escaped = ideas_json.replace("</script>", "<\\/script>")

    # 점수 스케일 감지
    max_score = kpi.get("score_max", 0.0)
    is_unit = max_score <= 1.5
    slider_max = 1.0 if is_unit else 100.0
    slider_step = 0.01 if is_unit else 1

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Daily Idea Ranking</title>

  <style>
    :root {{
      --bg: #0b0d12;
      --panel: rgba(255,255,255,0.06);
      --panel2: rgba(255,255,255,0.08);
      --text: rgba(255,255,255,0.92);
      --muted: rgba(255,255,255,0.62);
      --line: rgba(255,255,255,0.14);
      --chip: rgba(255,255,255,0.10);
      --shadow: 0 12px 44px rgba(0,0,0,0.45);
      --radius: 22px;
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--text);
      background:
        radial-gradient(900px 600px at 20% 10%, rgba(120,119,198,0.25), transparent 60%),
        radial-gradient(900px 600px at 80% 0%, rgba(34,211,238,0.18), transparent 55%),
        radial-gradient(900px 600px at 60% 90%, rgba(16,185,129,0.14), transparent 55%),
        var(--bg);
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
      letter-spacing: 0.2px;
    }}

    a {{ color: inherit; }}
    .wrap {{ max-width: 1180px; margin: 0 auto; padding: 26px 18px 64px; }}

    .topbar {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 14px;
    }}

    .headline h1 {{
      margin: 0;
      font-size: 26px;
      letter-spacing: -0.4px;
    }}
    .headline p {{
      margin: 7px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.35;
    }}

    .actions {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      justify-content: flex-end;
    }}

    .btn {{
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.10), rgba(255,255,255,0.06));
      color: var(--text);
      padding: 10px 12px;
      border-radius: 14px;
      cursor: pointer;
      font-weight: 700;
      font-size: 12px;
      text-decoration: none;
      box-shadow: 0 6px 22px rgba(0,0,0,0.25);
      transition: transform .12s ease, background .12s ease, border-color .12s ease;
      user-select: none;
    }}
    .btn:hover {{
      transform: translateY(-1px);
      border-color: rgba(255,255,255,0.25);
      background: linear-gradient(180deg, rgba(255,255,255,0.14), rgba(255,255,255,0.07));
    }}

    .grid {{
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 14px;
      margin-top: 12px;
    }}
    @media (max-width: 980px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}

    .panel {{
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.05));
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}

    .panel-head {{
      padding: 14px 14px 12px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }}

    .panel-title {{
      display: flex;
      gap: 10px;
      align-items: baseline;
      flex-wrap: wrap;
    }}
    .panel-title b {{ font-size: 14px; }}
    .panel-title span {{
      color: var(--muted);
      font-size: 12px;
    }}

    .kpi {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      padding: 14px;
    }}
    @media (max-width: 980px) {{
      .kpi {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}

    .kpi-card {{
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.05);
      border-radius: 18px;
      padding: 12px;
    }}
    .kpi-label {{
      color: var(--muted);
      font-size: 12px;
    }}
    .kpi-value {{
      margin-top: 5px;
      font-size: 20px;
      font-weight: 900;
      letter-spacing: -0.3px;
    }}
    .kpi-sub {{
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
    }}

    .controls {{
      padding: 12px 14px 14px;
      display: grid;
      grid-template-columns: 1.2fr 0.8fr 0.8fr;
      gap: 10px;
    }}
    @media (max-width: 980px) {{
      .controls {{ grid-template-columns: 1fr; }}
    }}

    .field {{
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.05);
      border-radius: 16px;
      padding: 10px 12px;
    }}
    .field label {{
      display: block;
      font-size: 11px;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    .field input[type="text"], .field select {{
      width: 100%;
      border: 0;
      outline: none;
      background: transparent;
      color: var(--text);
      font-size: 13px;
    }}
    .field input[type="range"] {{
      width: 100%;
    }}
    .field .row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }}
    .field .hint {{
      font-size: 12px;
      color: var(--muted);
      min-width: 76px;
      text-align: right;
    }}

    .tags {{
      padding: 0 14px 14px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .chip {{
      border: 1px solid var(--line);
      background: var(--chip);
      color: var(--text);
      font-size: 12px;
      padding: 7px 10px;
      border-radius: 999px;
      cursor: pointer;
      user-select: none;
      transition: transform .10s ease, border-color .12s ease, background .12s ease;
    }}
    .chip:hover {{
      transform: translateY(-1px);
      border-color: rgba(255,255,255,0.25);
      background: rgba(255,255,255,0.14);
    }}
    .chip.active {{
      border-color: rgba(34,211,238,0.55);
      background: rgba(34,211,238,0.14);
    }}
    .chip small {{
      color: var(--muted);
      font-weight: 700;
      margin-left: 6px;
    }}

    .list {{
      padding: 14px;
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
    }}

    .card {{
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.05);
      border-radius: 22px;
      padding: 14px;
      position: relative;
      overflow: hidden;
    }}

    .card-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
    }}

    .rank {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-weight: 900;
      font-size: 14px;
      padding: 7px 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.06);
      white-space: nowrap;
    }}
    .delta {{
      font-size: 12px;
      font-weight: 900;
      padding: 3px 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.06);
    }}
    .delta.up {{ border-color: rgba(34,197,94,0.45); background: rgba(34,197,94,0.10); }}
    .delta.down {{ border-color: rgba(239,68,68,0.45); background: rgba(239,68,68,0.10); }}
    .delta.new {{ border-color: rgba(59,130,246,0.55); background: rgba(59,130,246,0.12); }}
    .delta.same {{ color: var(--muted); }}

    .title {{
      font-size: 16px;
      font-weight: 900;
      letter-spacing: -0.2px;
      margin: 2px 0 6px;
    }}
    .meta {{
      color: var(--muted);
      font-size: 12px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .id {{
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.06);
      padding: 3px 8px;
      border-radius: 999px;
      font-size: 11px;
      color: var(--muted);
    }}

    .summary {{
      margin-top: 10px;
      color: rgba(255,255,255,0.82);
      font-size: 13px;
      line-height: 1.45;
    }}

    .pillrow {{
      margin-top: 10px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    
    .breakdown{{
      margin-top: 10px;
      padding: 10px;
      border: 1px solid rgba(255,255,255,0.10);
      border-radius: 16px;
      background: rgba(255,255,255,0.03);
      font-size: 12px;
    }}
    
    .breakdown-title{{
      font-weight: 900;
      opacity: 0.85;
      margin-bottom: 6px;
    }}
    
    .breakdown-row{{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 2px 0;
      opacity: 0.92;
    }}
    
    .breakdown-row b{{
      font-variant-numeric: tabular-nums;
    }}
    
    .pill {{
      font-size: 12px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.06);
      padding: 6px 9px;
      border-radius: 999px;
      color: var(--text);
    }}
    .pill.muted {{ color: var(--muted); }}

    .scorebox {{
      min-width: 210px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.05);
      border-radius: 18px;
      padding: 12px;
    }}

    .score-top {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 8px;
    }}
    .score-val {{
      font-size: 22px;
      font-weight: 950;
      letter-spacing: -0.4px;
    }}
    .score-badge {{
      font-size: 12px;
      font-weight: 900;
      border-radius: 999px;
      padding: 4px 8px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.06);
    }}
    .badge-high {{ border-color: rgba(34,197,94,0.45); background: rgba(34,197,94,0.10); }}
    .badge-mid {{ border-color: rgba(245,158,11,0.45); background: rgba(245,158,11,0.10); }}
    .badge-low {{ border-color: rgba(239,68,68,0.45); background: rgba(239,68,68,0.10); }}

    .bar {{
      margin-top: 10px;
      height: 10px;
      border-radius: 999px;
      background: rgba(255,255,255,0.08);
      overflow: hidden;
      border: 1px solid var(--line);
    }}
    .bar > i {{
      display: block;
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, rgba(34,211,238,0.75), rgba(120,119,198,0.75));
    }}

    details {{
      margin-top: 12px;
      border-top: 1px dashed rgba(255,255,255,0.18);
      padding-top: 10px;
    }}
    summary {{
      cursor: pointer;
      color: rgba(255,255,255,0.85);
      font-weight: 800;
      font-size: 13px;
      user-select: none;
    }}
    .detail-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-top: 10px;
    }}
    @media (max-width: 900px) {{
      .detail-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>

<body>
  <div class="wrap">
    <div class="topbar">
      <div class="headline">
        <h1>Daily Idea Ranking</h1>
        <p>
          Generated: {now} · Source: data/reports/idea_cards.json ·
          History: <a href="./history/index.html" style="text-decoration: underline;">open</a>
        </p>
      </div>

      <div class="actions">
        <a class="btn" href="./history/index.html">History</a>
        <button class="btn" id="btnReset">Reset filters</button>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <div class="panel-title">
          <b>Overview</b>
          <span>Top {len(table_rows)} · KPI & trend movement</span>
        </div>
        <div class="panel-title">
          <span>Score scale: {"0~1" if is_unit else "0~100"}</span>
        </div>
      </div>

      <div class="kpi">
        <div class="kpi-card">
          <div class="kpi-label">Ideas</div>
          <div class="kpi-value" id="kpiTotal">{kpi["total"]}</div>
          <div class="kpi-sub">Cards rendered today</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">NEW</div>
          <div class="kpi-value" id="kpiNew">{kpi["new"]}</div>
          <div class="kpi-sub">Not in previous snapshot</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Up / Down</div>
          <div class="kpi-value" id="kpiMove">{kpi["up"]} / {kpi["down"]}</div>
          <div class="kpi-sub">Rank delta vs previous day</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Avg / Max</div>
          <div class="kpi-value" id="kpiScore">{round(kpi["score_avg"], 3)} / {round(kpi["score_max"], 3)}</div>
          <div class="kpi-sub">Score distribution</div>
        </div>
      </div>

      <div class="controls">
        <div class="field">
          <label>Search (title / summary / tags)</label>
          <input id="q" type="text" placeholder="ex) security, rag, kubernetes..." />
        </div>

        <div class="field">
          <label>Sort</label>
          <select id="sort">
            <option value="rank_asc">Rank (best first)</option>
            <option value="score_desc">Score (high first)</option>
            <option value="delta_desc">Movement (up first)</option>
            <option value="evidence_desc">Evidence (many first)</option>
          </select>
        </div>

        <div class="field">
          <label>Min Score</label>
          <div class="row">
            <input id="minScore" type="range" min="0" max="{slider_max}" step="{slider_step}" value="0" />
            <div class="hint" id="minScoreLabel">0</div>
          </div>
        </div>
      </div>

      <div class="tags" id="tagChips">
        <div class="chip active" data-tag="__all__">All</div>
        {''.join([f'<div class="chip" data-tag="{_escape(t)}">{_escape(t)} <small>{c}</small></div>' for t, c in top_tags])}
      </div>

      <div class="list" id="list"></div>
    </div>
  </div>

  <script>
    const DATA = JSON.parse(`{ideas_json_escaped}`);
    const isUnit = {str(is_unit).lower()};

    const $list = document.getElementById("list");
    const $q = document.getElementById("q");
    const $sort = document.getElementById("sort");
    const $minScore = document.getElementById("minScore");
    const $minScoreLabel = document.getElementById("minScoreLabel");
    const $tagChips = document.getElementById("tagChips");
    const $btnReset = document.getElementById("btnReset");

    let activeTag = "__all__";

    function esc(s) {{
      return (s ?? "").toString()
        .replaceAll("&","&amp;")
        .replaceAll("<","&lt;")
        .replaceAll(">","&gt;")
        .replaceAll('"',"&quot;");
    }}

    function toNum(x, d=0) {{
      const n = Number(x);
      return Number.isFinite(n) ? n : d;
    }}

    function scoreOf(r) {{
      const s = (r.scores && typeof r.scores === "object") ? r.scores.total : r.total_score;
      return toNum(s, 0);
    }}

    function badgeClass(v) {{
      if (isUnit) {{
        if (v >= 0.75) return "badge-high";
        if (v >= 0.50) return "badge-mid";
        return "badge-low";
      }}
      if (v >= 75) return "badge-high";
      if (v >= 50) return "badge-mid";
      return "badge-low";
    }}

    function deltaSpan(d) {{
      if (d === null || d === undefined) return '<span class="delta new">NEW</span>';
      const n = toNum(d, 0);
      if (n > 0) return `<span class="delta up">↑ +${{n}}</span>`;
      if (n < 0) return `<span class="delta down">↓ ${{Math.abs(n)}}</span>`;
      return '<span class="delta same">–</span>';
    }}

    function fmtTags(tags) {{
      const arr = Array.isArray(tags) ? tags : (tags ? [tags] : []);
      return arr.slice(0, 10).map(t => `<span class="pill">${{esc(String(t))}}</span>`).join("");
    }}

    function matches(r, q) {{
      if (!q) return true;
      const text = (r.title + " " + (r.summary || "") + " " + (Array.isArray(r.tags) ? r.tags.join(" ") : "")).toLowerCase();
      return text.includes(q.toLowerCase());
    }}

    function tagOk(r) {{
      if (activeTag === "__all__") return true;
      const tags = Array.isArray(r.tags) ? r.tags : (r.tags ? [r.tags] : []);
      return tags.map(String).includes(activeTag);
    }}

    function render() {{
      const q = ($q.value || "").trim();
      const minS = toNum($minScore.value, 0);

      let rows = DATA.filter(r => matches(r, q) && tagOk(r) && scoreOf(r) >= minS);

      const sort = $sort.value;
      if (sort === "rank_asc") {{
        rows.sort((a,b) => toNum(a.rank, 1e9) - toNum(b.rank, 1e9));
      }} else if (sort === "score_desc") {{
        rows.sort((a,b) => scoreOf(b) - scoreOf(a));
      }} else if (sort === "delta_desc") {{
        rows.sort((a,b) => {{
          const da = (a.rank_delta === null || a.rank_delta === undefined) ? -9999 : toNum(a.rank_delta, 0);
          const db = (b.rank_delta === null || b.rank_delta === undefined) ? -9999 : toNum(b.rank_delta, 0);
          return db - da;
        }});
      }} else if (sort === "evidence_desc") {{
        rows.sort((a,b) => toNum(b.evidence_count, 0) - toNum(a.evidence_count, 0));
      }}

      $list.innerHTML = rows.map(r => {{
        const title = esc(r.title || "(untitled)");
        const ideaId = esc(String(r.idea_id || ""));
        const summary = esc(String(r.summary || "")).slice(0, 260);
        const tags = fmtTags(r.tags);
        const score = scoreOf(r);
        const pct = isUnit ? Math.max(0, Math.min(100, score * 100)) : Math.max(0, Math.min(100, score));
        const badge = badgeClass(score);
        const delta = deltaSpan(r.rank_delta);
        const evCount = toNum(r.evidence_count, 0);
        const bd = (r.score_breakdown && typeof r.score_breakdown === "object") ? r.score_breakdown : {{}};
        const bdKeys = Object.keys(bd);

        let bdHtml = "";
        if (bdKeys.length) {{
          bdHtml += '<div class="breakdown">';
          bdHtml += '<div class="breakdown-title">score breakdown</div>';
          for (const k of bdKeys) {{
            const kk = esc(String(k));
            const vv = toNum(bd[k], 0);
            bdHtml += '<div class="breakdown-row"><span>' + kk + '</span><b>' + (isUnit ? vv.toFixed(3) : vv.toFixed(2)) + '</b></div>';
          }}
          bdHtml += "</div>";
        }}
       
        

        return `
          <div class="card">
            <div class="card-head">
              <div>
                <div class="rank">#${{toNum(r.rank, 0)}} ${{delta}}</div>
                <div class="title">${{title}}</div>
                <div class="meta">
                  <span class="id">${{ideaId || "no-id"}}</span>
                  <span>Evidence: <b style="color: rgba(255,255,255,0.88);">${{evCount}}</b></span>
                </div>
                <div class="summary">${{summary}}</div>
                <div class="pillrow">${{tags || '<span class="pill muted">no tags</span>'}}</div>
                ${{bdHtml}}
              </div>

              <div class="scorebox">
                <div class="score-top">
                  <div class="score-val">${{isUnit ? score.toFixed(3) : score.toFixed(1)}}</div>
                  <div class="score-badge ${{badge}}">${{badge.replace("badge-","").toUpperCase()}}</div>
                </div>
                <div class="bar"><i style="width:${{pct}}%"></i></div>
              </div>
            </div>
          </div>
        `;
      }}).join("");
    }}

    function setMinLabel() {{
      const v = toNum($minScore.value, 0);
      $minScoreLabel.textContent = isUnit ? v.toFixed(2) : String(Math.round(v));
    }}

    $q.addEventListener("input", render);
    $sort.addEventListener("change", render);
    $minScore.addEventListener("input", () => {{
      setMinLabel();
      render();
    }});

    $tagChips.addEventListener("click", (e) => {{
      const el = e.target.closest(".chip");
      if (!el) return;
      const t = el.getAttribute("data-tag");
      if (!t) return;

      activeTag = t;
      [...$tagChips.querySelectorAll(".chip")].forEach(x => x.classList.remove("active"));
      el.classList.add("active");
      render();
    }});

    $btnReset.addEventListener("click", () => {{
      $q.value = "";
      $sort.value = "rank_asc";
      $minScore.value = 0;
      setMinLabel();
      activeTag = "__all__";
      [...$tagChips.querySelectorAll(".chip")].forEach(x => {{
        x.classList.toggle("active", x.getAttribute("data-tag") === "__all__");
      }});
      render();
    }});

    setMinLabel();
    render();
  </script>
</body>
</html>
"""


# =========================
# Outputs
# =========================
def save_daily_run_json(day: str, rows: list[dict]) -> Path:
    outdir = ROOT / "reports" / "daily"
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{day}.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main(top_n: int = 15) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    src = _pick_latest_file()
    rows = _load_rows(src)
    top = render_top_n(rows, n=top_n)

    today = _today_slug()
    daily_path = save_daily_run_json(today, top)
    print(f"🧷 Daily run saved -> {daily_path}")

    # ✅ rank delta 계산 (전날 스냅샷 기준) - snapshots.py가 list/dict 포맷 방지 로직 갖고 있어야 안정적
    prev_rank = load_prev_rank_map(today)
    for item in top:
        idea_id = item.get("idea_id") or ""
        prev = prev_rank.get(idea_id)
        item["rank_delta"] = None if prev is None else (prev - item["rank"])

    snap_json = write_history_snapshot_json(top, top_n=top_n)
    html = build_html(top)

    # 최신 index.html
    out = DOCS_DIR / "index.html"
    out.write_text(html, encoding="utf-8")

    # 날짜별 스냅샷 저장 + history index
    hist = write_history_snapshot(html)
    hist_index = write_history_index()

    print(f"✅ Rendered Top {top_n} -> {out}")
    print(f"🗂️ History snapshot -> {hist}")
    print(f"📜 History index -> {hist_index}")
    print(f"📥 Data source -> {src} (rows={len(rows)})")
    print(f"🧾 History data -> {snap_json}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topn", type=int, default=15, help="Top N to render for today")
    args = parser.parse_args()
    main(top_n=args.topn)