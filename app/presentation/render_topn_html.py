from __future__ import annotations
import sys
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]  # app/ 기준 2단계 위
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"

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
              <td class="rank">{r["rank"]}</td>
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


if __name__ == "__main__":
    n = 15
    if len(sys.argv) >= 2:
        try:
            n = int(sys.argv[1])
        except Exception:
            pass
    main(top_n=n)