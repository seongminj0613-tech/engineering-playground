from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, timezone
import json
import time
import uuid

@dataclass
class RunSummary:
    run_id: str
    date: str
    started_at: str
    finished_at: str | None = None
    duration_sec: float | None = None
    ingested: int = 0
    ranked: int = 0
    rendered: bool = False
    errors: int = 0
    notes: str | None = None

class RunTimer:
    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.t0 = time.time()
        now = datetime.now(timezone.utc)
        self.summary = RunSummary(
            run_id=str(uuid.uuid4())[:8],
            date=now.date().isoformat(),
            started_at=now.isoformat(),
        )

    def save(self) -> Path:
        if self.summary.finished_at is None:
            now = datetime.now(timezone.utc)
            self.summary.finished_at = now.isoformat()
            self.summary.duration_sec = round(time.time() - self.t0, 3)

        path = self.out_dir / f"{self.summary.date}_{self.summary.run_id}.json"
        path.write_text(json.dumps(asdict(self.summary), ensure_ascii=False, indent=2), encoding="utf-8")
        return path