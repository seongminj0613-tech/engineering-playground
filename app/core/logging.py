from __future__ import annotations
import json
import logging
import sys
from datetime import datetime, timezone

def setup_logger(level: str = "INFO", json_mode: bool = True) -> logging.Logger:
    logger = logging.getLogger("signalrank")
    logger.setLevel(level.upper())
    logger.handlers.clear()
    logger.propagate = False

    h = logging.StreamHandler(sys.stdout)
    h.setLevel(level.upper())

    if json_mode:
        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                payload = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "level": record.levelname,
                    "msg": record.getMessage(),
                    "name": record.name,
                }
                if record.exc_info:
                    payload["exc"] = self.formatException(record.exc_info)
                return json.dumps(payload, ensure_ascii=False)
        h.setFormatter(JsonFormatter())
    else:
        h.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    logger.addHandler(h)
    return logger