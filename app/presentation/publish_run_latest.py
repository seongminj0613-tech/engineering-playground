from __future__ import annotations
from pathlib import Path
import json

def main() -> int:
    runs_dir = Path("reports/runs")
    docs_dir = Path("docs")
    out_path = docs_dir / "run_latest.json"

    docs_dir.mkdir(parents=True, exist_ok=True)

    if not runs_dir.exists():
        out_path.write_text(
            json.dumps({"ok": False, "reason": "runs_dir_missing"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[publish_run_latest] runs_dir missing -> wrote {out_path}")
        return 0

    candidates = sorted(runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        out_path.write_text(
            json.dumps({"ok": False, "reason": "no_runs"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[publish_run_latest] no run files -> wrote {out_path}")
        return 0

    latest = candidates[0]
    data = json.loads(latest.read_text(encoding="utf-8"))
    data["ok"] = True
    data["source_file"] = str(latest).replace("\\", "/")

    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[publish_run_latest] wrote -> {out_path} (from {latest.name})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())