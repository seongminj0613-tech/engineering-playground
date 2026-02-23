from __future__ import annotations
from pathlib import Path


def load_meeting_text(meeting_path: str | Path) -> str:
    """
    베타 입력: .txt / .md 확실 지원
    확장: .docx / .hwp 는 나중에 adapter로 붙일 자리만 마련
    """
    p = Path(meeting_path)
    if not p.exists():
        raise FileNotFoundError(f"Meeting file not found: {p}")

    ext = p.suffix.lower()

    if ext in (".txt", ".md"):
        return p.read_text(encoding="utf-8", errors="ignore")

    # ---- 확장 슬롯 (Phase B) ----
    if ext == ".docx":
        raise NotImplementedError("DOCX input is not enabled yet. (Phase B)")
    if ext == ".hwp":
        raise NotImplementedError("HWP input is not enabled yet. (Phase B)")

    raise ValueError(f"Unsupported meeting file type: {ext} (use .txt/.md for beta)")