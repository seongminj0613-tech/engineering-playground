from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "data" / "reports" / "idea_cards.json"

def main():
    rows = json.loads(REPORT.read_text(encoding="utf-8"))
    bad = 0

    for r in rows:
        total = float(r.get("total_score", 0) or 0)
        bd = r.get("score_breakdown") or {}
        if isinstance(bd, dict) and bd:
            s = sum(float(v) for v in bd.values() if isinstance(v, (int, float)))
        else:
            s = 0.0

        if abs(total - s) > 0.01 and bd:
            bad += 1
            print(f"[MISMATCH] {r.get('idea_id')} total={total} sum(bd)={s} bd={bd}")

    if bad == 0:
        print("✅ OK: total_score == sum(score_breakdown) for all rows")
    else:
        print(f"❌ Found {bad} mismatches")

if __name__ == "__main__":
    main()