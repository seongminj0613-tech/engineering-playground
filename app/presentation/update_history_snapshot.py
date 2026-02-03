from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date as date_cls
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]  # app/presentation -> app -> repo root
DEFAULT_INPUT = ROOT / "data" / "reports" / "idea_cards.json"
HISTORY_DATA_DIR = ROOT / "docs" / "history" / "data"
HISTORY_INDEX_PATH = HISTORY_DATA_DIR / "index.json"


@dataclass
class SnapshotItem:
    idea_id: str
    rank: int
    total_score: float
    title: str
    tags: List[str]


def _today_ymd() -> str:
    return date_cls.today().isoformat()


def _safe_get(d: Dict[str, Any], keys: List[str], default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def load_idea_cards(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Input not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
        return data["items"]
    if isinstance(data, list):
        return data
    raise ValueError("Unsupported idea_cards.json format (expected list or {items:[...]})")


def normalize_topn(items: List[Dict[str, Any]], topn: int) -> List[SnapshotItem]:
    # v1 구조가 어떤지 100% 모르니 최대한 관대하게 뽑음
    norm: List[SnapshotItem] = []
    for i, raw in enumerate(items[:topn], start=1):
        idea_id = str(raw.get("idea_id") or raw.get("id") or raw.get("key") or "")
        if not idea_id:
            # idea_id 없으면 히스토리 트래킹이 깨지니 강제 생성은 비추.
            # 일단 스킵 (원하면 여기서 해시 기반 생성 로직 넣자)
            continue

        title = str(raw.get("title") or raw.get("name") or raw.get("idea_title") or idea_id)

        tags = raw.get("tags") or raw.get("tag") or []
        if isinstance(tags, str):
            tags = [tags]
        if not isinstance(tags, list):
            tags = []

        # 점수 키들도 흔들릴 수 있어서 여러 후보를 봄
        total_score = (
            raw.get("total_score")
            or raw.get("score")
            or _safe_get(raw, ["scores", "total"])
            or _safe_get(raw, ["score", "total"])
            or 0.0
        )
        try:
            total_score = float(total_score)
        except Exception:
            total_score = 0.0

        norm.append(
            SnapshotItem(
                idea_id=idea_id,
                rank=i,
                total_score=total_score,
                title=title,
                tags=[str(t) for t in tags],
            )
        )
    return norm


def ensure_history_index() -> Dict[str, Any]:
    HISTORY_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if HISTORY_INDEX_PATH.exists():
        try:
            return json.loads(HISTORY_INDEX_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"dates": []}


def write_snapshot(snapshot_date: str, items: List[SnapshotItem]) -> Path:
    out_path = HISTORY_DATA_DIR / f"{snapshot_date}.json"
    payload = {
        "date": snapshot_date,
        "topn": len(items),
        "items": [
            {
                "idea_id": x.idea_id,
                "rank": x.rank,
                "total_score": x.total_score,
                "title": x.title,
                "tags": x.tags,
            }
            for x in items
        ],
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def update_index(snapshot_date: str) -> None:
    idx = ensure_history_index()
    dates = idx.get("dates") if isinstance(idx.get("dates"), list) else []
    if snapshot_date not in dates:
        dates.append(snapshot_date)
    dates = sorted(set(dates))
    idx["dates"] = dates
    HISTORY_INDEX_PATH.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")


def main(
    input_path: Optional[str] = None,
    snapshot_date: Optional[str] = None,
    topn: int = 20,
) -> None:
    in_path = Path(input_path) if input_path else DEFAULT_INPUT
    d = snapshot_date or _today_ymd()

    raw_items = load_idea_cards(in_path)
    top_items = normalize_topn(raw_items, topn=topn)

    snap_path = write_snapshot(d, top_items)
    update_index(d)
    print(f"[history] wrote snapshot: {snap_path} (items={len(top_items)})")


if __name__ == "__main__":
    main()