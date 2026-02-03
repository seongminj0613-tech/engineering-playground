from __future__ import annotations
import sys
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]  # app/ 기준 2단계 위
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"

HISTORY_DIR = DOCS_DIR / "history"
HISTORY_DATA_DIR = HISTORY_DIR / "data"
HISTORY_INDEX_JSON = HISTORY_DATA_DIR / "index.json"

# ✅ 너 프로젝트에서 "최신 결과" 파일명에 맞춰서 하나만 쓰면 됨
CANDIDATES = [
    DATA_DIR / "reports" / "idea_cards.json",
    DATA_DIR / "registry" / "ideas.jsonl",
    DATA_DIR / "raw" / "ideas.jsonl",
]


def _load_rows(path: Path) -> list[dict]:
    if path.suffix == ".json":
        obj = json.loads(path.read_text(encoding="utf-8"))

        # ✅ case A: list[dict]
        if isinstance(obj, list):
            return obj

        # ✅ case B: {"items":[...]} or {"ideas":[...]} or {"cards":[...]}
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


def render_top_n(rows: list[dict], n: int = 15) -> list[dict]:
    """
    idea_cards.json row schema:
    - title, summary, tags, trend
    - scores: dict (contains total/feasibility/risk/etc)
    - evidence/risks/assumptions: list or dict or str
    """
    def pick_total_score(r: dict) -> float:
        s = r.get("scores") or {}
        if isinstance(s, dict):
            # 흔한 후보 키들
            for k in ["total", "total_score", "final", "final_score", "score"]:
                if k in s:
                    return _to_float(s.get(k))
            # dict 안에 숫자 중 가장 큰 값(보험)
            nums = [v for v in s.values() if isinstance(v, (int, float))]
            if nums:
                return float(max(nums))
        return 0.0

    ranked = sorted(rows, key=pick_total_score, reverse=True)[:n]

    out = []
    for i, r in enumerate(ranked, start=1):
        out.append(
            {
                "rank": i,
                "idea_id": r.get("idea_id", ""),
                "title": r.get("title", "(untitled)"),
                "summary": r.get("summary", ""),
                "tags": r.get("tags", []),
                "trend": r.get("trend", ""),
                "scores": r.get("scores", {}),
                "evidence": r.get("evidence", []),
                "risks": r.get("risks", []),
                "assumptions": r.get("assumptions", []),
            }
        )
    return out

def build_html(table_rows: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    def fmt_tags(tags):
        if isinstance(tags, list):
            return "".join(f'<span class="tag">{_escape(str(t))}</span>' for t in tags[:8])
        if tags:
            return f'<span class="tag">{_escape(str(tags))}</span>'
        return ""

    def fmt_trend(tr):
        tr = (tr or "").strip()
        if not tr:
            return ""
        # 흔한 값 가정: up/down/flat or ↑ ↓ →
        m = tr.lower()
        if m in ["up", "rising", "increase", "increasing"]:
            return '<span class="trend up">↑</span>'
        if m in ["down", "falling", "decrease", "decreasing"]:
            return '<span class="trend down">↓</span>'
        if m in ["flat", "same", "stable"]:
            return '<span class="trend flat">→</span>'
        return f'<span class="trend flat">{_escape(tr)}</span>'

    def fmt_scores(scores):
        if not isinstance(scores, dict) or not scores:
            return ""
        # total을 우선 보여주되, 나머지는 작은 글씨로
        total = None
        for k in ["total", "total_score", "final", "final_score", "score"]:
            if k in scores:
                total = scores.get(k)
                break
        if total is None:
            nums = [v for v in scores.values() if isinstance(v, (int, float))]
            total = max(nums) if nums else 0

        total_f = _to_float(total)
        badge_cls = "score mid"
        if total_f >= 80:
            badge_cls = "score high"
        elif total_f >= 50:
            badge_cls = "score mid"
        else:
            badge_cls = "score low"

        # 상세 점수(숫자만 4개까지)
        parts = []
        for k, v in scores.items():
            if isinstance(v, (int, float)) and k not in ["total", "total_score", "final", "final_score", "score"]:
                parts.append(f"{_escape(str(k))}:{round(float(v), 2)}")
        detail = ", ".join(parts[:4])

        return f"""
        <div class="{badge_cls}">{round(total_f, 2)}</div>
        <div class="small">{_escape(detail)}</div>
        """.strip()

    def fmt_list(x):
        # evidence/risks/assumptions가 list/dict/str 아무거나 와도 대응
        if x is None:
            return ""
        if isinstance(x, str):
            return f"<li>{_escape(x)}</li>"
        if isinstance(x, dict):
            items = [f"<li><b>{_escape(str(k))}</b>: {_escape(str(v))}</li>" for k, v in x.items()]
            return "\n".join(items)
        if isinstance(x, list):
            items = []
            for it in x[:10]:
                if isinstance(it, dict):
                    # dict 안에 핵심 텍스트 후보
                    txt = it.get("text") or it.get("summary") or it.get("title") or str(it)
                    url = it.get("url") or it.get("source") or ""
                    if url and (str(url).startswith("http://") or str(url).startswith("https://")):
                        items.append(f'<li><a href="{_escape(str(url))}" target="_blank" rel="noopener noreferrer">{_escape(str(txt))}</a></li>')
                    else:
                        items.append(f"<li>{_escape(str(txt))}</li>")
                else:
                    items.append(f"<li>{_escape(str(it))}</li>")
            return "\n".join(items)
        return f"<li>{_escape(str(x))}</li>"

    trs = []
    for r in table_rows:
        title = _escape(r["title"])
        summary = _escape(str(r.get("summary", ""))[:220])
        idea_id = _escape(str(r.get("idea_id", "")))
        
        delta = r.get("rank_delta", None)

        if delta is None:
            delta_html = '<span class="delta new">NEW</span>'
        elif delta > 0:
            delta_html = f'<span class="delta up">↑ +{delta}</span>'
        elif delta < 0:
            delta_html = f'<span class="delta down">↓ {abs(delta)}</span>'
        else:
            delta_html = '<span class="delta same">–</span>'

        detail_html = f"""
        <div class="detail-grid">
          <div>
            <h4>Evidence</h4>
            <ul>{fmt_list(r.get("evidence"))}</ul>
          </div>
          <div>
            <h4>Risks</h4>
            <ul>{fmt_list(r.get("risks"))}</ul>
          </div>
          <div>
            <h4>Assumptions</h4>
            <ul>{fmt_list(r.get("assumptions"))}</ul>
          </div>
        </div>
        """.strip()

        trs.append(
           f"""
           <tr>
            <td class="rank">{r["rank"]} {delta_html}</td>
            <td>
              <div class="title-row">
                <span class="title">{title}</span>
                <span class="id">{idea_id}</span>
             </div>
             <div class="summary">{summary}</div>
             <div class="tags">{fmt_tags(r.get("tags"))}</div>

             <details>
               <summary>Details</summary>
               {detail_html}
             </details>
          </td>
          <td class="scorecell">{fmt_scores(r.get("scores"))}</td>
          <td class="trendcell">{fmt_trend(r.get("trend"))}</td>
          </tr>
          """.strip()
      )

    trs_html = "\n".join(trs)
    ideas_json = json.dumps(table_rows, ensure_ascii=False)
    ideas_json_escaped = ideas_json.replace("</script>", "<\\/script>")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Daily Idea Ranking</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }}
    h1 {{ margin: 0 0 6px; }}
    .meta {{ color: #666; margin-bottom: 16px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #e5e5e5; padding: 12px; vertical-align: top; }}
    th {{ background: #f7f7f7; text-align: left; }}
    tr:hover {{ background: #fcfcfc; }}

    .rank {{ width: 60px; font-weight: 700; }}
    .title-row {{ display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }}
    .title {{ font-weight: 700; font-size: 15px; }}
    .id {{ color: #888; font-size: 12px; }}
    .summary {{ margin-top: 6px; color: #333; }}
    .tags {{ margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }}
    .tag {{ border: 1px solid #ddd; padding: 2px 8px; border-radius: 999px; font-size: 12px; color: #333; background: #fafafa; }}
    .controls {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin: 14px 0 10px; }}
    .input {{ padding: 10px 12px; border: 1px solid #ddd; border-radius: 10px; min-width: 260px; }}
    .select {{ padding: 10px 12px; border: 1px solid #ddd; border-radius: 10px; }}
    .slider-wrap {{ display: flex; gap: 8px; align-items: center; }}
    .btn {{ padding: 10px 12px; border: 1px solid #ddd; border-radius: 10px; background: #fafafa; cursor: pointer; }}
    .btn:hover {{ background: #f2f2f2; }}
   
   
    .delta {{ margin-left: 6px; font-weight: 800; font-size: 12px; }} 
    .delta.up {{ color: #16a34a; }}
    .delta.down {{ color: #dc2626; }}
    .delta.new {{ color: #2563eb; }}
    .delta.same {{ color: #6b7280; }}
    
    .scorecell {{ width: 140px; }}
    .score {{ display: inline-block; padding: 6px 10px; border-radius: 10px; font-weight: 800; }}
    .score.high {{ background: #eaffea; border: 1px solid #b8f0b8; }}
    .score.mid {{ background: #fff7e6; border: 1px solid #ffe0a3; }}
    .score.low {{ background: #ffecec; border: 1px solid #ffbdbd; }}
    .small {{ font-size: 12px; color: #666; margin-top: 6px; }}

    .trendcell {{ width: 90px; text-align: center; font-size: 18px; }}
    .trend {{ display: inline-block; padding: 4px 8px; border-radius: 10px; border: 1px solid #e5e5e5; }}
    .trend.up {{ background: #eaffea; }}
    .trend.down {{ background: #ffecec; }}
    .trend.flat {{ background: #f4f4f4; }}

    details {{ margin-top: 10px; }}
    summary {{ cursor: pointer; color: #333; }}
    .detail-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 12px; }}
    .detail-grid h4 {{ margin: 0 0 6px; font-size: 13px; }}
    ul {{ margin: 0; padding-left: 18px; }}
    li {{ margin-bottom: 6px; }}
    @media (max-width: 900px) {{
      .detail-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <h1>Daily Idea Ranking</h1>
    <div class="controls">
    <input id="q" class="input" type="search" placeholder="Search title / summary / idea_id..." />
    <select id="tag" class="select">
      <option value="">All tags</option>
    </select>

    <div class="slider-wrap">
      <label for="topn">Top N:</label>
      <input id="topn" type="range" min="5" max="200" step="1" value="15" />
      <span id="topnVal">15</span>
    </div>

    <button id="clear" class="btn" type="button">Clear</button>
  </div>

  <div class="meta" id="meta2"></div>
  
  <div class="meta">Generated: {now} · Source: data/reports/idea_cards.json · Showing Top {len(table_rows)}</div>

  <table>
    <thead>
      <tr>
        <th style="width:60px;">Rank</th>
        <th>Idea</th>
        <th style="width:140px;">Score</th>
        <th style="width:90px;">Trend</th>
      </tr>
    </thead>
    <tbody>
      {trs_html}
    </tbody>
  </table>
  <script id="ideas-data" type="application/json">{ideas_json_escaped}</script>
  <script>
    window.__IDEAS__ = {ideas_json};
  </script>

 
  <script>
  (() => {{
    const raw = document.getElementById('ideas-data')?.textContent || "[]";
    let IDEAS = [];
    try {{
      IDEAS = JSON.parse(raw);
    }} catch (e) {{
      console.error("Failed to parse ideas JSON:", e);
      IDEAS = [];
    }}

    IDEAS = IDEAS.map(x => ({{
      ...x,
      _title: String(x.title || '').toLowerCase(),
      _summary: String(x.summary || '').toLowerCase(),
      _id: String(x.idea_id || '').toLowerCase(),
      _tags: Array.isArray(x.tags) ? x.tags.map(t => String(t)) : (x.tags ? [String(x.tags)] : [])
    }}));

    const qEl = document.getElementById('q');
    const tagEl = document.getElementById('tag');
    const topnEl = document.getElementById('topn');
    const topnVal = document.getElementById('topnVal');
    const meta2 = document.getElementById('meta2');
    const clearBtn = document.getElementById('clear');

    if (!qEl || !tagEl || !topnEl || !topnVal || !meta2 || !clearBtn) {{
      console.error("UI elements not found. Did you add the controls block?");
      return;
    }}

    const maxN = Math.max(5, IDEAS.length);
    topnEl.max = String(maxN);
    if (Number(topnEl.value) > maxN) topnEl.value = String(Math.min(15, maxN));
    topnVal.textContent = topnEl.value;

    // tags dropdown 채우기
    const tagSet = new Set();
    IDEAS.forEach(x => x._tags.forEach(t => tagSet.add(t)));
    Array.from(tagSet).sort((a,b)=>a.localeCompare(b)).forEach(t => {{
      const opt = document.createElement('option');
      opt.value = t;
      opt.textContent = t;
      tagEl.appendChild(opt);
    }});

    function esc(s) {{
      return String(s ?? '')
        .replaceAll('&','&amp;')
        .replaceAll('<','&lt;')
        .replaceAll('>','&gt;')
        .replaceAll('"','&quot;');
    }}

    function passes(x, q, tag) {{
      if (tag && !x._tags.includes(tag)) return false;
      if (q) {{
        if (!(x._title.includes(q) || x._summary.includes(q) || x._id.includes(q))) return false;
      }}
      return true;
    }}

    function fmtDelta(delta) {{
      if (delta === null || delta === undefined) return '<span class="delta new">NEW</span>';
      if (delta > 0) return `<span class="delta up">↑ +${{delta}}</span>`;
      if (delta < 0) return `<span class="delta down">↓ ${{Math.abs(delta)}}</span>`;
      return '<span class="delta same">–</span>';
    }}

    function render() {{
      const q = (qEl.value || '').trim().toLowerCase();
      const tag = tagEl.value || '';
      const n = Number(topnEl.value || 15);
      topnVal.textContent = String(n);

      const filtered = IDEAS.filter(x => passes(x, q, tag));
      const shown = filtered.slice(0, n);

      const tbody = document.querySelector('table tbody');
      tbody.innerHTML = shown.map(r => {{
        const deltaHtml = fmtDelta(r.rank_delta);
        const tagsHtml = (r._tags || []).slice(0,8).map(t => `<span class="tag">${{esc(t)}}</span>`).join('');

        return `
          <tr>
            <td class="rank">${{r.rank}} ${{deltaHtml}}</td>
            <td>
              <div class="title-row">
                <span class="title">${{esc(r.title || '(untitled)')}}</span>
                <span class="id">${{esc(r.idea_id || '')}}</span>
              </div>
              <div class="summary">${{esc(String(r.summary || '').slice(0,220))}}</div>
              <div class="tags">${{tagsHtml}}</div>
            </td>
            <td class="scorecell"><div class="small">Filtered view</div></td>
            <td class="trendcell"></td>
          </tr>
        `;
      }}).join('');

      meta2.textContent = `Filtered: ${{filtered.length}} / ${{IDEAS.length}} · Showing: ${{Math.min(n, filtered.length)}}`;
    }}

    [qEl, tagEl, topnEl].forEach(el => el.addEventListener('input', render));
    clearBtn.addEventListener('click', () => {{
      qEl.value = '';
      tagEl.value = '';
      topnEl.value = String(Math.min(15, maxN));
      render();
    }});

    render();
  }})();
  </script>

  <p class="small">Next: auto-generate this page in GitHub Actions + add /history pages.</p>
  
  <p class="small">
  History: <a href="./history/index.html">Open history</a>
  </p>
</body>
</html>
"""


def _today_slug() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def write_history_index() -> Path:
    history_dir = DOCS_DIR / "history"
    history_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(history_dir.glob("*.html"), reverse=True)
    links = "\n".join(
        f'<li><a href="{f.name}">{f.stem}</a></li>'
        for f in files
        if f.name != "index.html"
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>History</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }}
    a {{ text-decoration: none; }}
  </style>
</head>
<body>
  <h1>History</h1>
  <p><a href="../index.html">← Back to latest</a></p>
  <ul>
    {links}
  </ul>
</body>
</html>
"""
    out = history_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


def write_history_snapshot(html: str) -> Path:
    """
    Save today's snapshot into docs/history/YYYY-MM-DD.html
    """
    history_dir = DOCS_DIR / "history"
    history_dir.mkdir(parents=True, exist_ok=True)

    out = history_dir / f"{_today_slug()}.html"
    out.write_text(html, encoding="utf-8")
    return out

def _ensure_history_data_dir() -> None:
    HISTORY_DATA_DIR.mkdir(parents=True, exist_ok=True)


def write_history_snapshot_json(table_rows: list[dict], top_n: int) -> Path:
    """
    Save today's snapshot into docs/history/data/YYYY-MM-DD.json
    (idea_id 기준 rank/score/title/tags 저장)
    """
    _ensure_history_data_dir()
    day = _today_slug()

    payload = {
        "date": day,
        "topn": top_n,
        "items": [
            {
                "idea_id": r.get("idea_id", ""),
                "rank": r.get("rank", None),
                "title": r.get("title", ""),
                "tags": r.get("tags", []),
                "total_score": _to_float((r.get("scores") or {}).get("total", (r.get("scores") or {}).get("total_score", 0.0))),
            }
            for r in table_rows
            if r.get("idea_id")
        ],
    }

    out = HISTORY_DATA_DIR / f"{day}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # index.json 업데이트
    idx = {"dates": []}
    if HISTORY_INDEX_JSON.exists():
        try:
            idx = json.loads(HISTORY_INDEX_JSON.read_text(encoding="utf-8"))
        except Exception:
            idx = {"dates": []}

    dates = idx.get("dates", [])
    if not isinstance(dates, list):
        dates = []
    if day not in dates:
        dates.append(day)

    idx["dates"] = sorted(set(dates))
    HISTORY_INDEX_JSON.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")

    return out

def load_prev_rank_map(today: str) -> dict[str, int]:
    """
    return: {idea_id: prev_rank}
    """
    if not HISTORY_INDEX_JSON.exists():
        return {}

    try:
        idx = json.loads(HISTORY_INDEX_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}

    dates = idx.get("dates", [])
    if not isinstance(dates, list):
        return {}

    prev_candidates = [d for d in dates if isinstance(d, str) and d < today]
    if not prev_candidates:
        return {}

    prev = prev_candidates[-1]
    snap = HISTORY_DATA_DIR / f"{prev}.json"
    if not snap.exists():
        return {}

    try:
        data = json.loads(snap.read_text(encoding="utf-8"))
    except Exception:
        return {}

    m = {}
    for it in data.get("items", []):
        idea_id = it.get("idea_id")
        rank = it.get("rank")
        if idea_id and isinstance(rank, int):
            m[str(idea_id)] = rank
    return m


def _escape(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _link_or_text(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("http://") or s.startswith("https://"):
        esc = _escape(s)
        return f'<a href="{esc}" target="_blank" rel="noopener noreferrer">{esc}</a>'
    return _escape(s)


def main(top_n: int = 15) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    src = _pick_latest_file()
    rows = _load_rows(src)
    top = render_top_n(rows, n=top_n)
    
    today = _today_slug()
    prev_rank = load_prev_rank_map(today)

    for item in top:
        idea_id = item.get("idea_id") or ""
        prev = prev_rank.get(idea_id)

        if prev is None:
            item["rank_delta"] = None  # NEW
        else:
            item["rank_delta"] = prev - item["rank"]  # +면 상승
            
    snap_json = write_history_snapshot_json(top, top_n=top_n)

    html = build_html(top)

    # 1) 최신 index.html
    out = DOCS_DIR / "index.html"
    out.write_text(html, encoding="utf-8")

    # 2) 날짜별 스냅샷 저장
    hist = write_history_snapshot(html)

    # 3) history/index.html 생성(링크 목록 페이지)
    hist_index = write_history_index()

    # 로그
    print(f"✅ Rendered Top {top_n} -> {out}")
    print(f"🗂️ History snapshot -> {hist}")
    print(f"📜 History index -> {hist_index}")
    print(f"📥 Data source -> {src} (rows={len(rows)})")
    print(f"🧾 History data -> {snap_json}")


if __name__ == "__main__":
    n = 15
    if len(sys.argv) >= 2:
        try:
            n = int(sys.argv[1])
        except Exception:
            pass
    main(top_n=n)