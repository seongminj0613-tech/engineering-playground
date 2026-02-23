from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class MeetingIdea:
    title: str
    reason: str
    raw: str


@dataclass
class DroppedIdea:
    raw: str
    reason: str


_BULLET_RE = re.compile(r"^\s*[-*•]\s+(.*)$")
_TITLE_HINT_RE = re.compile(r"^\s*(아이디어|제목|idea|title)\s*[:：]\s*(.+)$", re.I)
_REASON_HINT_RE = re.compile(r"^\s*(이유|근거|설명|reason|why)\s*[:：]\s*(.+)$", re.I)

_NEW_IDEA_RE = _TITLE_HINT_RE


def parse_meeting_text(text: str, min_len: int = 3, min_title_len: int = 2) -> List[MeetingIdea]:
    ideas, _dropped = parse_meeting_text_with_dropped(
        text=text,
        min_len=min_len,
        min_title_len=min_title_len,
    )
    return ideas


def parse_meeting_text_with_dropped(
    text: str,
    min_len: int = 3,
    min_title_len: int = 2,
) -> Tuple[List[MeetingIdea], List[DroppedIdea]]:
    """
    parse_meeting_text와 동일한 파싱 로직을 사용하되,
    버려진 블록/라인을 dropped로 함께 반환한다.

    Returns:
      (ideas, dropped)
    """
    lines = [ln.rstrip() for ln in text.splitlines()]

    blocks: List[List[str]] = []
    cur: List[str] = []

    dropped: List[DroppedIdea] = []

    def flush():
        if cur:
            blocks.append(cur.copy())
            cur.clear()

    for ln in lines:
        s = ln.strip()
        if not s:
            flush()
            continue

        if cur and _TITLE_HINT_RE.match(s):
            flush()

        cur.append(s)

    flush()

    ideas: List[MeetingIdea] = []

    for b in blocks:
        raw = "\n".join(b).strip()

        if len(raw) < min_len:
            dropped.append(DroppedIdea(raw=raw, reason=f"block_too_short(min_len={min_len})"))
            continue

        title = ""
        reason_parts: List[str] = []

        for ln in b:
            m1 = _TITLE_HINT_RE.match(ln)
            if m1 and not title:
                title = m1.group(2).strip()
                continue

            m2 = _REASON_HINT_RE.match(ln)
            if m2:
                reason_parts.append(m2.group(2).strip())
                continue

            mb = _BULLET_RE.match(ln)
            if mb and not title:
                title = mb.group(1).strip()
                continue

        if not title:
            title = b[0].strip()

        if reason_parts:
            reason = " ".join(reason_parts).strip()[:600]
        else:
            rest = [x.strip() for x in b[1:] if x.strip()]
            reason = " ".join(rest).strip()[:600]

        title = title.strip()
        if len(title) < min_title_len:
            dropped.append(DroppedIdea(raw=raw, reason=f"title_too_short(min_title_len={min_title_len})"))
            continue

        ideas.append(MeetingIdea(title=title, reason=reason, raw=raw))

    # 중복 제거 (+ dropped 기록)
    seen = set()
    uniq: List[MeetingIdea] = []
    for it in ideas:
        k = it.title.lower().strip()
        if k in seen:
            dropped.append(DroppedIdea(raw=it.raw, reason="duplicate_title"))
            continue
        seen.add(k)
        uniq.append(it)

    return uniq, dropped