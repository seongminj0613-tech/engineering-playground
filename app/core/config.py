from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
import yaml
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class AppConfig:
    top_k: int = 15
    run_dir: Path = Path("reports/runs")
    daily_dir: Path = Path("reports/daily")
    docs_dir: Path = Path("docs")
    log_level: str = "INFO"
    log_json: bool = True

def load_config(path: str = "config.yaml") -> AppConfig:
    cfg = {}
    if Path(path).exists():
        cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

    scoring = cfg.get("scoring", {})
    paths = cfg.get("paths", {})
    logging = cfg.get("logging", {})

    return AppConfig(
        top_k=int(os.getenv("SIGNALRANK_TOP_K", scoring.get("top_k", 15))),
        run_dir=Path(os.getenv("SIGNALRANK_RUN_DIR", paths.get("run_dir", "reports/runs"))),
        daily_dir=Path(os.getenv("SIGNALRANK_DAILY_DIR", paths.get("daily_dir", "reports/daily"))),
        docs_dir=Path(os.getenv("SIGNALRANK_DOCS_DIR", paths.get("docs_dir", "docs"))),
        log_level=os.getenv("SIGNALRANK_LOG_LEVEL", logging.get("level", "INFO")),
        log_json=str(logging.get("json", "true")).lower() in ("1", "true", "yes", "y"),
    )