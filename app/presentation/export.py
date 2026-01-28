from __future__ import annotations
import json
from pathlib import Path
from typing import List
from .idea_card import IdeaCard

def export_cards_json(cards: List[IdeaCard], out_path: str) -> str:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [c.model_dump() for c in cards]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)