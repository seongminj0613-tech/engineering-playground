from __future__ import annotations
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

def _stable_doc_id(source: str, url: str, title: str) -> str:
    s = f"{source}|{url}|{title}".encode("utf-8")
    h = hashlib.sha1(s).hexdigest()[:12]
    return f"{source}_{h}"

def append_external_docs(path: Path, docs: list[dict]) -> int:
    """
    docs: [{source,title,url,snippet,tags,published_at}]
    - doc_id 없으면 생성
    - url/title 기준으로 중복 방지
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    seen: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                key = (d.get("source",""), d.get("url",""), d.get("title",""))
                seen.add(str(key))
            except Exception:
                continue

    out_lines = []
    added = 0
    now_iso = datetime.now(timezone.utc).date().isoformat()

    for d in docs:
        source = str(d.get("source") or "unknown")
        title = str(d.get("title") or "")
        url = str(d.get("url") or "")
        if not title and not url:
            continue

        key = str((source, url, title))
        if key in seen:
            continue

        doc_id = d.get("doc_id") or _stable_doc_id(source, url, title)
        tags = d.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]

        rec = {
            "doc_id": doc_id,
            "source": source,
            "title": title,
            "url": url,
            "snippet": str(d.get("snippet") or ""),
            "tags": tags,
            "published_at": str(d.get("published_at") or now_iso),
        }

        out_lines.append(json.dumps(rec, ensure_ascii=False))
        seen.add(key)
        added += 1

    if out_lines:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(out_lines) + "\n")

    return added