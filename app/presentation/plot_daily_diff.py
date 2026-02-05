from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, UTC

ROOT = Path(__file__).resolve().parents[2]  # app/presentation -> repo root
HISTORY_DIR = ROOT / "docs" / "history"
SNAP_DIR = HISTORY_DIR / "data"

DIFF_DIR = HISTORY_DIR / "diff"
DIFF_DATA_DIR = DIFF_DIR / "data"
DIFF_INDEX_PATH = DIFF_DIR / "index.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


@dataclass
class IdeaRow:
    idea_id: str
    title: str
    rank: int
    score: float
    raw: Dict[str, Any]


def normalize_snapshot(snapshot: Any) -> List[IdeaRow]:
    """
    snapshot 파일 포맷이 리스트든/딕트든 최대한 유연하게 대응.
    기대 필드(추정): idea_id, title, total_score(or score), rank
    """
    if isinstance(snapshot, dict):
        # 흔한 케이스: {"items": [...]} / {"ideas": [...]} / {"cards": [...]}
        for key in ("items", "ideas", "cards", "data", "rows"):
            if key in snapshot and isinstance(snapshot[key], list):
                snapshot = snapshot[key]
                break

    if not isinstance(snapshot, list):
        return []

    rows: List[IdeaRow] = []
    for i, r in enumerate(snapshot):
        if not isinstance(r, dict):
            continue

        idea_id = str(r.get("idea_id") or r.get("id") or r.get("key") or f"row_{i}")
        title = str(r.get("title") or r.get("name") or r.get("summary") or "")
        rank = safe_int(r.get("rank"), default=i + 1)
        score = safe_float(
            r.get("total_score", r.get("score", r.get("final_score", 0.0))),
            default=0.0,
        )
        rows.append(IdeaRow(idea_id=idea_id, title=title, rank=rank, score=score, raw=r))
    return rows


def get_last_two_dates_from_index() -> Optional[Tuple[str, str]]:
    """
    docs/history/data/index.json 에 날짜 리스트가 있다고 가정.
    형태가 달라도 최대한 맞춰봄.
    """
    index_path = SNAP_DIR / "index.json"
    if not index_path.exists():
        return None

    idx = load_json(index_path)

    dates: List[str] = []
    if isinstance(idx, list):
        dates = [str(x) for x in idx]
    elif isinstance(idx, dict):
        # {"dates":[...]} or {"items":[{"date":...}, ...]}
        if isinstance(idx.get("dates"), list):
            dates = [str(x) for x in idx["dates"]]
        elif isinstance(idx.get("items"), list):
            for it in idx["items"]:
                if isinstance(it, dict) and "date" in it:
                    dates.append(str(it["date"]))

    dates = [d for d in dates if d]
    # 날짜 정렬(YYYY-MM-DD)
    def key(d: str) -> str:
        return d

    dates = sorted(set(dates), key=key)
    if len(dates) < 2:
        return None
    return dates[-2], dates[-1]


def compute_diff(prev_rows: List[IdeaRow], curr_rows: List[IdeaRow]) -> Dict[str, Any]:
    prev_map = {r.idea_id: r for r in prev_rows}
    curr_map = {r.idea_id: r for r in curr_rows}

    appeared = [cid for cid in curr_map.keys() if cid not in prev_map]
    disappeared = [pid for pid in prev_map.keys() if pid not in curr_map]

    changed: List[Dict[str, Any]] = []
    for idea_id, c in curr_map.items():
        p = prev_map.get(idea_id)
        if p is None:
            changed.append(
                {
                    "idea_id": idea_id,
                    "title": c.title,
                    "status": "NEW",
                    "rank_prev": None,
                    "rank_curr": c.rank,
                    "rank_delta": None,
                    "score_prev": None,
                    "score_curr": c.score,
                    "score_delta": None,
                }
            )
            continue

        rank_delta = p.rank - c.rank  # +면 순위 상승(예: 10->7 => +3)
        score_delta = c.score - p.score

        changed.append(
            {
                "idea_id": idea_id,
                "title": c.title or p.title,
                "status": "EXISTING",
                "rank_prev": p.rank,
                "rank_curr": c.rank,
                "rank_delta": rank_delta,
                "score_prev": p.score,
                "score_curr": c.score,
                "score_delta": score_delta,
            }
        )

    # 정렬 우선순위: NEW 먼저, 그 다음 rank_delta 큰 순, score_delta 큰 순
    def sort_key(x: Dict[str, Any]) -> Tuple[int, float, float]:
        status = x["status"]
        status_key = 0 if status == "NEW" else 1
        rd = x["rank_delta"]
        sd = x["score_delta"]
        rdv = float(rd) if rd is not None else -9999.0
        sdv = float(sd) if sd is not None else -9999.0
        return (status_key, -rdv, -sdv)

    changed_sorted = sorted(changed, key=sort_key)

    return {
        "summary": {
            "curr_count": len(curr_rows),
            "prev_count": len(prev_rows),
            "new_count": len(appeared),
            "disappeared_count": len(disappeared),
        },
        "new_ids": appeared,
        "disappeared_ids": disappeared,
        "rows": changed_sorted,
    }


def render_html(date_prev: str, date_curr: str, diff: Dict[str, Any]) -> str:
    s = diff["summary"]
    rows = diff["rows"]

    def fmt(v: Any) -> str:
        if v is None:
            return "-"
        if isinstance(v, float):
            return f"{v:.3f}"
        return str(v)

    # rank_delta: +면 상승, -면 하락, 0 유지
    def fmt_rank_delta(v: Any) -> str:
        if v is None:
            return "-"
        v = int(v)
        if v > 0:
            return f"▲ {v}"
        if v < 0:
            return f"▼ {abs(v)}"
        return "• 0"

    def fmt_score_delta(v: Any) -> str:
        if v is None:
            return "-"
        v = float(v)
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.3f}"

    trs = []
    for r in rows[:200]:  # 너무 길어지면 200개 컷
        trs.append(
            f"""
            <tr>
              <td>{r["status"]}</td>
              <td>{r["idea_id"]}</td>
              <td>{(r["title"] or "")[:120]}</td>
              <td style="text-align:right">{fmt(r["rank_prev"])}</td>
              <td style="text-align:right">{fmt(r["rank_curr"])}</td>
              <td style="text-align:right">{fmt_rank_delta(r["rank_delta"])}</td>
              <td style="text-align:right">{fmt(r["score_prev"])}</td>
              <td style="text-align:right">{fmt(r["score_curr"])}</td>
              <td style="text-align:right">{fmt_score_delta(r["score_delta"])}</td>
            </tr>
            """
        )

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Daily Diff {date_curr} (vs {date_prev})</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 24px; }}
    h1 {{ margin: 0 0 8px 0; }}
    .meta {{ color: #555; margin-bottom: 16px; }}
    .chips span {{ display:inline-block; padding:6px 10px; border:1px solid #ddd; border-radius:999px; margin-right:8px; font-size:13px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #eee; padding: 10px 8px; vertical-align: top; font-size: 13px; }}
    th {{ text-align: left; position: sticky; top: 0; background: #fff; }}
    tr:hover td {{ background: #fafafa; }}
    .footer {{ margin-top: 18px; color:#777; font-size: 12px; }}
    code {{ background:#f6f6f6; padding:2px 6px; border-radius:6px; }}
  </style>
</head>
<body>
  <h1>Daily Diff: {date_curr}</h1>
  <div class="meta">비교 기준: <code>{date_prev}</code> → <code>{date_curr}</code></div>

  <div class="chips" style="margin-bottom: 14px;">
    <span>현재: {s["curr_count"]}</span>
    <span>전날: {s["prev_count"]}</span>
    <span>NEW: {s["new_count"]}</span>
    <span>사라짐: {s["disappeared_count"]}</span>
  </div>

  <table>
    <thead>
      <tr>
        <th>Status</th>
        <th>idea_id</th>
        <th>title</th>
        <th style="text-align:right">rank(D-1)</th>
        <th style="text-align:right">rank(D)</th>
        <th style="text-align:right">Δrank</th>
        <th style="text-align:right">score(D-1)</th>
        <th style="text-align:right">score(D)</th>
        <th style="text-align:right">Δscore</th>
      </tr>
    </thead>
    <tbody>
      {''.join(trs)}
    </tbody>
  </table>

  <div class="footer">
    생성: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")}
  </div>
</body>
</html>"""


def update_diff_index(date_curr: str) -> None:
    dates: List[str] = []
    if DIFF_INDEX_PATH.exists():
        try:
            obj = load_json(DIFF_INDEX_PATH)
            if isinstance(obj, list):
                dates = [str(x) for x in obj]
            elif isinstance(obj, dict) and isinstance(obj.get("dates"), list):
                dates = [str(x) for x in obj["dates"]]
        except Exception:
            dates = []

    if date_curr not in dates:
        dates.append(date_curr)
    dates = sorted(set(dates))
    dump_json(DIFF_INDEX_PATH, dates)


def main() -> None:
    last_two = get_last_two_dates_from_index()
    if not last_two:
        print("⚠️ Not enough history dates to compute D-1 diff.")
        return

    date_prev, date_curr = last_two
    prev_path = SNAP_DIR / f"{date_prev}.json"
    curr_path = SNAP_DIR / f"{date_curr}.json"

    if not prev_path.exists() or not curr_path.exists():
        print(f"⚠️ Missing snapshot file: {prev_path} or {curr_path}")
        return

    prev_rows = normalize_snapshot(load_json(prev_path))
    curr_rows = normalize_snapshot(load_json(curr_path))

    diff = compute_diff(prev_rows, curr_rows)

    # save json
    diff_json_path = DIFF_DATA_DIR / f"{date_curr}.json"
    dump_json(
        diff_json_path,
        {"date_prev": date_prev, "date_curr": date_curr, **diff},
    )

    # save html
    diff_html_path = DIFF_DIR / f"{date_curr}.html"
    diff_html_path.parent.mkdir(parents=True, exist_ok=True)
    diff_html_path.write_text(render_html(date_prev, date_curr, diff), encoding="utf-8")

    # update index
    update_diff_index(date_curr)

    print(f"✅ diff saved: {diff_json_path}")
    print(f"✅ diff page:  {diff_html_path}")


if __name__ == "__main__":
    main()