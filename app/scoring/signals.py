from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional


TECH_KEYWORDS = {
    "kubernetes", "docker", "terraform", "cloudformation", "aws", "gcp", "azure",
    "rag", "retrieval", "vector", "llm", "agent", "inference", "gpu", "serverless",
    "observability", "prometheus", "grafana", "kafka", "spark", "airflow",
}

MARKET_KEYWORDS = {
    "roi", "cost", "reduce", "efficiency", "automation", "compliance", "security",
    "enterprise", "b2b", "subscription", "revenue", "margin", "workflow",
}

EVIDENCE_MARKERS = {
    "study", "paper", "dataset", "benchmark", "report", "metrics", "data",
    "github", "docs", "reference", "link", "source",
}


def _safe_text(idea: Dict[str, Any]) -> str:
    parts = [
        str(idea.get("title", "")),
        str(idea.get("summary", "")),
        str(idea.get("description", "")),
        str(idea.get("content", "")),
        " ".join(map(str, idea.get("tags", []) or [])),
    ]
    return " ".join(p for p in parts if p).strip().lower()


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _count_keywords(text: str, keywords: set[str]) -> int:
    return sum(1 for kw in keywords if kw in text)


def _specificity(text: str) -> float:
    # 숫자/고유패턴/기술키워드가 많을수록 구체적
    digits = len(re.findall(r"\d", text))
    urls = len(re.findall(r"https?://", text))
    codey = len(re.findall(r"`.+?`", text))
    tech = _count_keywords(text, TECH_KEYWORDS)

    raw = 0.25 * digits + 1.5 * urls + 1.0 * codey + 0.8 * tech
    return _clamp01(_sigmoid((raw - 2.0) / 3.0))  # 대충 0~1로


def _clarity(text: str) -> float:
    # 너무 짧으면 정보 부족, 너무 길면 산만(대충)
    n = len(text.split())
    if n <= 10:
        return 0.2
    if n <= 30:
        return 0.7
    if n <= 120:
        return 0.9
    if n <= 220:
        return 0.7
    return 0.5


def _evidence(text: str, idea: Dict[str, Any]) -> float:
    markers = _count_keywords(text, EVIDENCE_MARKERS)
    has_url = ("http://" in text) or ("https://" in text)
    src = str(idea.get("source", "")).lower()
    # HN 같은 곳이면 기본 근거 약간
    base = 0.15 if src in {"hn", "hackernews"} else 0.05
    raw = base + (0.15 * markers) + (0.25 if has_url else 0.0)
    return _clamp01(raw)


def _market_pull(text: str) -> float:
    hits = _count_keywords(text, MARKET_KEYWORDS)
    return _clamp01(_sigmoid((hits - 1.0) / 2.0))


def _feasibility(text: str) -> float:
    # 과장/허황 키워드 있으면 감점, 구체성 있으면 가점
    hype = 1 if any(k in text for k in ["revolutionary", "magic", "guaranteed", "instant"]) else 0
    spec = _specificity(text)
    raw = 0.6 * spec - 0.25 * hype + 0.4
    return _clamp01(raw)


def _novelty(text: str, corpus_counter: Optional[Counter] = None) -> float:
    # 단어가 흔할수록 novelty 낮음 (아주 단순 근사)
    if not corpus_counter:
        return 0.6  # 코퍼스 없으면 중간값
    tokens = [t for t in re.findall(r"[a-z0-9]+", text) if len(t) >= 4]
    if not tokens:
        return 0.5
    avg_freq = sum(corpus_counter.get(t, 0) for t in tokens) / max(1, len(tokens))
    # freq 높으면 novelty 낮아짐
    return _clamp01(1.0 - _sigmoid((avg_freq - 2.0) / 3.0))


def build_corpus_counter(ideas: List[Dict[str, Any]]) -> Counter:
    c = Counter()
    for idea in ideas:
        text = _safe_text(idea)
        tokens = [t for t in re.findall(r"[a-z0-9]+", text) if len(t) >= 4]
        c.update(tokens)
    return c


def extract_signals(
    idea: Dict[str, Any],
    *,
    corpus_counter: Optional[Counter] = None,
    trend_score: float = 0.0,   # 0~1
    freshness: float = 0.0,     # 0~1
) -> Dict[str, float]:
    text = _safe_text(idea)

    signals = {
        "novelty": _novelty(text, corpus_counter),
        "specificity": _specificity(text),
        "feasibility": _feasibility(text),
        "market_pull": _market_pull(text),
        "evidence": _evidence(text, idea),
        "clarity": _clarity(text),
        "trend_boost": _clamp01(trend_score),
        "freshness": _clamp01(freshness),
    }

    # 최소 안전장치: 값이 None/NaN이면 0으로
    for k, v in list(signals.items()):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            signals[k] = 0.0

    return signals