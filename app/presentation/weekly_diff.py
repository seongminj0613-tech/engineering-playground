import json
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[2]
HISTORY = ROOT / "docs" / "history" / "data"
OUT = ROOT / "docs" / "history" / "weekly_diff.json"


def load_snapshot(date_str):
    path = HISTORY / f"{date_str}.json"
    if not path.exists():
        return {}

    with open(path, encoding="utf-8") as f:
        obj = json.load(f)

    # ✅ list로 저장된 경우 (reports/daily 구조)
    if isinstance(obj, list):
        rows = obj

    # ✅ dict 구조 (history snapshot 구조)
    elif isinstance(obj, dict):
        rows = obj.get("items", obj.get("rows", obj.get("data", [])))

    else:
        rows = []

    return {r.get("idea_id"): r for r in rows if isinstance(r, dict) and r.get("idea_id")}

def main():
    with open(HISTORY / "index.json", encoding="utf-8") as f:
        index = json.load(f)
        dates = sorted(index["dates"])

    latest = dates[-1]
    target = (datetime.fromisoformat(latest) - timedelta(days=7)).date().isoformat()
    prev = max([d for d in dates if d <= target], default=dates[0])
    
    cur = load_snapshot(latest)
    old = load_snapshot(prev)

    diff = {}
    for k in cur.keys() & old.keys():
        diff[k] = {
            "score_delta": round(cur[k]["total_score"] - old[k]["total_score"], 3),
            "rank_delta": cur[k]["rank"] - old[k]["rank"],
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(diff, indent=2), encoding="utf-8")
    print(f"weekly diff saved → {OUT}")


if __name__ == "__main__":
    main()