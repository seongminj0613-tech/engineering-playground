import json
from pathlib import Path


def render_json(report_dir: Path, payload: dict):
    report_dir.mkdir(parents=True, exist_ok=True)

    out_path = report_dir / "data.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"📦 data.json saved → {out_path}")