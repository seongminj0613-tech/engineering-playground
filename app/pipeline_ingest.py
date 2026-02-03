# app/pipeline_ingest.py
import json
import re, unicodedata, hashlib
from pathlib import Path
from datetime import datetime
from collections import Counter
from difflib import SequenceMatcher

from app.signals.signals import build_signals_from_disclosure

ROOT = Path(__file__).resolve().parents[1]
IDEA_REGISTRY_PATH = ROOT / "data" / "registry" / "ideas.jsonl"
REVIEW_PATH = ROOT / "data" / "review" / "pending_ideas.jsonl"

def load_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            
STOPWORDS = {"서비스","플랫폼","시스템","프로젝트","기능","개발","구현","자동","관리"}

def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s).lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s가-힣]", " ", s)
    toks = [t for t in s.split() if t and t not in STOPWORDS]
    return "".join(toks)

def extract_keywords(text: str, top_n: int = 5):
    raw = unicodedata.normalize("NFKC", (text or "")).lower()
    raw = re.sub(r"[^\w\s가-힣]", " ", raw)
    toks = [t for t in raw.split() if len(t) >= 2 and t not in STOPWORDS]
    return [w for w,_ in Counter(toks).most_common(top_n)]

def make_norm_key(title: str, text: str = "") -> str:
    nt = normalize_text(title)
    kws = extract_keywords(text or title, top_n=5)
    base = nt + "|" + "|".join(sorted(kws))
    h = hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]
    return f"k:{h}"

def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()

def jaccard(a_set, b_set) -> float:
    if not a_set and not b_set:
        return 0.0
    return len(a_set & b_set) / max(1, len(a_set | b_set))

def fuzzy_score(in_title: str, in_text: str, cand: dict) -> float:
    s1 = title_similarity(in_title, cand.get("title",""))
    in_k = set(extract_keywords(in_text or in_title))
    ca_k = set(extract_keywords(cand.get("title","")))
    s2 = jaccard(in_k, ca_k)
    return 0.75*s1 + 0.25*s2

AUTO_MATCH_THRESHOLD = 0.90
REVIEW_THRESHOLD = 0.80

def load_registry(path: Path):
    return load_jsonl(path)  # 이미 jsonl loader 있으니 재사용

def save_registry(rows, path: Path):
    write_jsonl(path, rows)

def build_index(ideas):
    by_key = {}
    for it in ideas:
        for k in it.get("norm_keys", []):
            by_key[k] = it["idea_id"]
    return by_key

def next_idea_id(ideas):
    mx = 0
    for it in ideas:
        try:
            mx = max(mx, int(it["idea_id"].split("_")[1]))
        except:
            pass
    return f"IDEA_{mx+1:07d}"

def ingest_assign_idea_id(doc: dict, registry_ideas: list):
    title = doc.get("title","") or ""
    text  = doc.get("text","") or ""
    norm_key = make_norm_key(title, text)

    idx = build_index(registry_ideas)

    # 1) 확정 매칭 (norm_key)
    if norm_key in idx:
        idea_id = idx[norm_key]
        return idea_id, {"matched_by":"norm_key","confidence":1.0,"matched_to":idea_id,"needs_review":False}, registry_ideas

    # 2) fuzzy 후보 찾기
    best, best_score = None, 0.0
    for cand in registry_ideas:
        sc = fuzzy_score(title, text, cand)
        if sc > best_score:
            best, best_score = cand, sc

    # 2-1) 자동 매칭
    if best and best_score >= AUTO_MATCH_THRESHOLD:
        idea_id = best["idea_id"]
        best.setdefault("norm_keys", [])
        if norm_key not in best["norm_keys"]:
            best["norm_keys"].append(norm_key)
        return idea_id, {"matched_by":"fuzzy","confidence":round(best_score,4),"matched_to":idea_id,"needs_review":False}, registry_ideas

    # 2-2) 리뷰로 보류 (새 ID 만들지 않음)
    if best and best_score >= REVIEW_THRESHOLD:
        return None, {"matched_by":"review","confidence":round(best_score,4),"matched_to":best["idea_id"],"needs_review":True}, registry_ideas

    # 3) 신규 생성
    new_id = next_idea_id(registry_ideas)
    registry_ideas.append({
        "idea_id": new_id,
        "title": title,
        "norm_title": normalize_text(title),
        "aliases": [],
        "norm_keys": [norm_key],
    })
    return new_id, {"matched_by":"new","confidence":1.0,"matched_to":new_id,"needs_review":False}, registry_ideas


def normalize_disclosure(doc: dict) -> dict:
    """
    공시/공개데이터 문서 dict를 signals 생성기가 기대하는 최소 포맷으로 맞춤.
    네 실제 필드명에 맞춰서 여기만 바꾸면 전체가 다 돌아감.
    """
    title = doc.get("title") or doc.get("report_nm") or doc.get("corp_cls") or ""
    text = doc.get("text") or doc.get("content") or doc.get("body") or ""
    published_at = doc.get("published_at") or doc.get("rcept_dt") or doc.get("date") or ""
    entity = doc.get("entity") or doc.get("corp_name") or doc.get("corp_nm") or ""
    doc_id = doc.get("doc_id") or doc.get("rcept_no") or doc.get("id") or ""
    url = doc.get("url") or doc.get("link") or None

    # 날짜가 YYYYMMDD면 YYYY-MM-DD로 바꿔줌
    if isinstance(published_at, str) and len(published_at) == 8 and published_at.isdigit():
        published_at = f"{published_at[:4]}-{published_at[4:6]}-{published_at[6:8]}"

    return {
        "doc_id": str(doc_id),
        "source": doc.get("source", "dart"),
        "published_at": str(published_at),
        "entity": str(entity),
        "title": str(title),
        "text": str(text),
        "url": url,
        # 원본도 같이 들고가면 디버깅이 쉬움(원하면 삭제 가능)
        "_raw": doc,
    }


def main():
    print("🚀 Ingest pipeline started")

    in_path = ROOT / "data" / "raw" / "disclosures.jsonl"
    out_path = ROOT / "data" / "raw" / "signals.jsonl"

    docs_raw = load_jsonl(in_path)
    print(f"loaded disclosures: {len(docs_raw)} ({in_path})")

    registry = load_registry(IDEA_REGISTRY_PATH)
    pending = []
    signals_all = []

    for d in docs_raw:
        doc = normalize_disclosure(d)

        idea_id, match, registry = ingest_assign_idea_id(doc, registry)
        doc["idea_id"] = idea_id
        doc["match"] = match

        sigs = build_signals_from_disclosure(doc)
        for s in sigs:
            s["idea_id"] = idea_id if idea_id else None
            s["review_target"] = match.get("matched_to")
            s["match"] = match

        if match.get("needs_review"):
            pending.append({
                "title": doc.get("title",""),
                "text": doc.get("text","")[:5000],
                "proposed": match.get("matched_to"),
                "confidence": match.get("confidence"),
            })

        signals_all.extend(sigs)
        
        save_registry(registry, IDEA_REGISTRY_PATH)

        if pending:
            write_jsonl(REVIEW_PATH, pending)

        write_jsonl(out_path, signals_all)
    print(f"wrote signals: {len(signals_all)} ({out_path})")

   
if __name__ == "__main__":
    main()