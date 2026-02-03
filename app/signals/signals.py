# app/signals/signals.py
from typing import Dict, List
import re
from datetime import datetime

RULES = [
    ("contract_award", ["공급계약", "수주", "계약체결"], 0.8, 0.85),
    ("funding", ["유상증자", "전환사채", "신주"], 0.75, 0.85),
    ("risk_flag", ["소송", "횡령", "배임", "감사의견"], 0.9, 0.9),
]

def build_signals_from_disclosure(doc: Dict) -> List[Dict]:
    """
    doc 예시:
    {
      "doc_id": "...",
      "title": "...",
      "text": "...",
      "published_at": "2026-01-30",
      "entity": "삼성전자",
      "url": "..."
    }
    """
    signals: List[Dict] = []

    title = doc.get("title", "")
    text = doc.get("text", "")
    content = f"{title}\n{text}"

    for sig_type, keywords, value, confidence in RULES:
        for kw in keywords:
            if kw in content:
                signals.append({
                    "type": sig_type,
                    "source": "dart",
                    "date": doc.get("published_at"),
                    "entity": doc.get("entity"),
                    "title": title,
                    "value": value,
                    "confidence": confidence,
                    "evidence": {
                        "doc_id": doc.get("doc_id"),
                        "url": doc.get("url"),
                        "snippet": title[:120],
                    }
                })
                break

    return signals