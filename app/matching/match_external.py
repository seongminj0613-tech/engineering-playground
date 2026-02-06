from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Iterable

STOPWORDS = {
    "trend","trends","trending","issue","issues","update","news","new",
    "the","a","an","and","or","to","of","in","on","for","with","by","at","from",
    "is","are","was","were","be","been","being","as","it","this","that",
    # 한국어는 형태소 안 쓰고 최소만 (너무 세게 걸면 매칭 0 나옴)
    "이","그","저","것","수","등","및","대한","관련","위한","통한","에서","으로",
    "트렌드","이슈","뉴스","최신","업데이트",
}

def load_external_docs(path: Path) -> list[dict]:
    docs: list[dict] = []
    if not path.exists():
        return docs
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            docs.append(json.loads(line))
        except Exception:
            # 깨진 라인 하나 때문에 전체 실패 방지
            continue
    return docs

def _tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    # 단어/숫자/한글 토큰 대충 분리 (v1은 룰 기반)
    raw = re.findall(r"[a-z0-9]+|[가-힣]+", text)
    toks = []
    for t in raw:
        if len(t) < 2:
            continue
        if t in STOPWORDS:
            continue
        toks.append(t)
    return toks

def extract_terms(*parts: str, max_terms: int = 25) -> list[str]:
    toks: list[str] = []
    for p in parts:
        toks.extend(_tokenize(p))
    # 빈도 기반 상위만 (간단)
    freq: dict[str, int] = {}
    for t in toks:
        freq[t] = freq.get(t, 0) + 1
    ranked = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
    return [k for k, _ in ranked[:max_terms]]

def score_relevance(idea_terms: Iterable[str], doc: dict) -> tuple[float, list[str]]:
    title = str(doc.get("title", "") or "")
    snippet = str(doc.get("snippet", "") or "")
    tags = doc.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    tags_text = " ".join([str(x) for x in tags])

    doc_terms = set(extract_terms(title, snippet, tags_text, max_terms=40))
    idea_set = set([str(t) for t in idea_terms])

    overlap = sorted(list(idea_set & doc_terms))
    if not overlap:
        return 0.0, []

    # 가중치: title에 겹치면 +, tags 겹치면 + (아주 단순한 v1)
    title_terms = set(extract_terms(title, max_terms=40))
    tags_terms = set(extract_terms(tags_text, max_terms=40))
    base = float(len(overlap))
    bonus = 0.0
    bonus += 0.8 * len(idea_set & title_terms)
    bonus += 0.5 * len(idea_set & tags_terms)

    return base + bonus, overlap[:10]

def match_evidence_for_idea(idea: dict, docs: list[dict], top_n: int = 3) -> list[dict]:
    title = str(idea.get("title", "") or idea.get("idea", "") or "")
    summary = str(idea.get("summary", "") or idea.get("description", "") or "")
    content = str(idea.get("content", "") or "")

    tags = idea.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    tags_text = " ".join([str(t) for t in tags])

    signals = idea.get("signals") or {}
    signal_keys = " ".join(list(signals.keys())) if isinstance(signals, dict) else ""

    idea_terms = extract_terms(title, summary, content, tags_text, signal_keys, max_terms=40)

    # ✅ 중요: scored 리스트 선언
    scored: list[tuple[float, dict]] = []

    for d in docs:
        s, overlap = score_relevance(idea_terms, d)

        # 점수 없는건 제외
        if s <= 0:
            continue

        ev = {
            "doc_id": d.get("doc_id"),
            "source": d.get("source"),
            "title": d.get("title"),
            "url": d.get("url"),
            "published_at": d.get("published_at"),
            "relevance": round(float(s), 3),
            "overlap_terms": overlap,
        }

        scored.append((float(s), ev))
def compute_market_signal(evidence: list[dict]) -> float:
    # v1: evidence 개수 + relevance 합 (간단/직관)
    if not evidence:
        return 0.0
    return round(
        len(evidence) * 1.0
        + sum(float(e.get("relevance", 0) or 0) for e in evidence) * 0.2,
        3,
    )

    # 점수순 정렬
    scored.sort(key=lambda x: x[0], reverse=True)

    return [ev for _, ev in scored[:top_n]]