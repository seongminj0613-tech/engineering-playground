from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Any

# ---------------------------
# Path helpers
# ---------------------------

def _project_root() -> Path:
    """
    app/history/snapshots.py 기준으로
    ROOT = 프로젝트 루트(= app 폴더의 상위)로 잡는다.
    """
    return Path(__file__).resolve().parents[2]

def _docs_dir() -> Path:
    return _project_root() / "docs"

def _history_dir() -> Path:
    return _docs_dir() / "history"

def _history_data_dir() -> Path:
    return _history_dir() / "data"

def _history_index_json() -> Path:
    return _history_data_dir() / "index.json"


def _today_slug() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def _ensure_history_data_dir() -> None:
    _history_data_dir().mkdir(parents=True, exist_ok=True)


# ---------------------------
# Robust JSON parsing helpers
# ---------------------------

def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def _extract_items(obj: Any) -> list[dict]:
    """
    ✅ 핵심: history snapshot json이
    - dict: {"items":[...]}  형태일 수도 있고
    - list: [{...}, {...}]   형태일 수도 있음

    어디든 안전하게 list[dict]로 변환해서 리턴.
    """
    if obj is None:
        return []

    # case A) list 자체가 items
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]

    # case B) dict 안에 items
    if isinstance(obj, dict):
        items = obj.get("items", [])
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]
        return []

    return []


def _to_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


# ---------------------------
# Write helpers
# ---------------------------

def write_history_snapshot(html: str, day: str | None = None) -> Path:
    """
    docs/history/YYYY-MM-DD.html 저장
    """
    day = day or _today_slug()
    out_dir = _history_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    out = out_dir / f"{day}.html"
    out.write_text(html, encoding="utf-8")
    return out


def write_history_index() -> Path:
    """
    docs/history/index.html (링크 목록)
    """
    history_dir = _history_dir()
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


def write_history_snapshot_json(table_rows: list[dict], top_n: int, day: str | None = None) -> Path:
    """
    docs/history/data/YYYY-MM-DD.json 저장
    (idea_id 기준 rank/title/tags/total_score만 저장)

    ✅ 여기서 포맷을 'dict + items'로 고정해두면
    다른 곳에서 list/dict 섞임으로 생기는 에러가 줄어듦.
    """
    _ensure_history_data_dir()
    day = day or _today_slug()

    payload = {
        "date": day,
        "topn": top_n,
        "items": [
            {
                "idea_id": r.get("idea_id", ""),
                "rank": r.get("rank", None),
                "title": r.get("title", ""),
                "tags": r.get("tags", []),
                "total_score": _to_float(
                    r.get("total_score")
                    or (r.get("scores") or {}).get("total")
                    or (r.get("scores") or {}).get("total_score")
                    or 0.0
                ),
            }
            for r in table_rows
            if r.get("idea_id")
        ],
    }

    out = _history_data_dir() / f"{day}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # index.json 업데이트
    index_path = _history_index_json()
    idx = {"dates": []}
    if index_path.exists():
        try:
            idx_obj = _read_json(index_path)
            if isinstance(idx_obj, dict) and isinstance(idx_obj.get("dates"), list):
                idx = idx_obj
        except Exception:
            idx = {"dates": []}

    dates = idx.get("dates", [])
    if not isinstance(dates, list):
        dates = []

    if day not in dates:
        dates.append(day)

    idx["dates"] = sorted(set([d for d in dates if isinstance(d, str)]))
    index_path.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")

    return out


# ---------------------------
# Load helpers
# ---------------------------

def load_history_snapshot_json(day: str) -> list[dict]:
    """
    docs/history/data/YYYY-MM-DD.json 로드 후,
    build_html()이 요구하는 table_rows 형태로 변환
    """
    snap = _history_data_dir() / f"{day}.json"
    if not snap.exists():
        raise FileNotFoundError(f"History snapshot json not found: {snap}")

    obj = _read_json(snap)
    items = _extract_items(obj)

    table_rows = []
    for it in items:
        table_rows.append(
            {
                "rank": int(it.get("rank") or 0),
                "idea_id": it.get("idea_id", ""),
                "title": it.get("title", "(untitled)"),
                "summary": "",
                "tags": it.get("tags", []),
                "trend": "",
                "total_score": _to_float(it.get("total_score", 0.0)),
                "scores": {"total": _to_float(it.get("total_score", 0.0))},
                "evidence": [],
                "risks": [],
                "assumptions": [],
            }
        )

    # rank 오름차순 정렬
    table_rows = sorted(table_rows, key=lambda r: r.get("rank", 10**9))
    return table_rows


def load_prev_rank_map(today: str) -> dict[str, int]:
    """
    return: {idea_id: prev_rank}
    ✅ 여기서 list/dict 포맷 섞여도 절대 안 터지게 방어
    """
    index_path = _history_index_json()
    if not index_path.exists():
        return {}

    try:
        idx = _read_json(index_path)
    except Exception:
        return {}

    dates = idx.get("dates", []) if isinstance(idx, dict) else []
    if not isinstance(dates, list):
        return {}

    prev_candidates = [d for d in dates if isinstance(d, str) and d < today]
    if not prev_candidates:
        return {}

    prev = sorted(prev_candidates)[-1]
    snap = _history_data_dir() / f"{prev}.json"
    if not snap.exists():
        return {}

    try:
        data_obj = _read_json(snap)
    except Exception:
        return {}

    items = _extract_items(data_obj)

    m: dict[str, int] = {}
    for it in items:
        idea_id = it.get("idea_id")
        rank = it.get("rank")
        if idea_id and isinstance(rank, int):
            m[str(idea_id)] = rank
        elif idea_id and isinstance(rank, (str, float)):
            # 문자열/float로 들어와도 안전 변환
            try:
                m[str(idea_id)] = int(rank)
            except Exception:
                pass

    return m


# ---------------------------
# Rebuild helpers
# ---------------------------

def write_history_snapshot_for_date(html: str, day: str) -> Path:
    return write_history_snapshot(html, day=day)


def rebuild_history_pages(build_html_fn) -> None:
    """
    docs/history/data/index.json의 dates 전체를 읽어
    각 날짜별 HTML을 다시 만든다.

    사용법:
      from app.history.snapshots import rebuild_history_pages
      rebuild_history_pages(build_html)

    (build_html_fn은 render_topn_html.py의 build_html 함수를 넘겨주면 됨)
    """
    index_path = _history_index_json()
    if not index_path.exists():
        print("⚠️ No history index.json found. Nothing to rebuild.")
        return

    try:
        idx = _read_json(index_path)
    except Exception:
        print("⚠️ Failed to read history index.json. Nothing to rebuild.")
        return

    dates = idx.get("dates", []) if isinstance(idx, dict) else []
    if not isinstance(dates, list) or not dates:
        print("⚠️ No dates in history index.json. Nothing to rebuild.")
        return

    ok = 0
    for day in sorted([d for d in dates if isinstance(d, str)]):
        try:
            table_rows = load_history_snapshot_json(day)
            html = build_html_fn(table_rows)
            out = write_history_snapshot_for_date(html, day)
            ok += 1
            print(f"✅ Rebuilt history page -> {out}")
        except Exception as e:
            print(f"❌ Failed to rebuild {day}: {e}")

    hist_index = write_history_index()
    print(f"📜 History index -> {hist_index} (rebuilt {ok} pages)")