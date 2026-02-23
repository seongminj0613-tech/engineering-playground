from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from app.server.viewmodel import build_viewmodel_from_meeting_text
from app.ingestion.meeting_parse import parse_meeting_text_with_dropped

import re

ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT / "web"

app = FastAPI(title="Meeting Decision Engine (Local)", version="0.1.0")

# 로컬 개발 편의용 (프론트가 다른 포트에서 열릴 수 있으니)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
def home():
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        return "<h3>web/index.html not found</h3>"
    return index_path.read_text(encoding="utf-8")


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    topn: int = Query(10, ge=1, le=50),
    mode: str = Query("balanced"),
    evidence: str = Query("none"),   # "none" | "external" (나중에 확장)
):
    # 파일 타입 제한 (md/txt)
    filename = (file.filename or "").lower()
    if not (filename.endswith(".md") or filename.endswith(".txt")):
        raise HTTPException(status_code=400, detail="Only .md or .txt supported")

    raw = await file.read()
    try:
        meeting_text = raw.decode("utf-8")
        meeting_text = re.sub(r"\s*(아이디어\s*[:：])\s*", r"\n\1 ", meeting_text).strip()
    except UnicodeDecodeError:
        # 윈도우 메모장/한글 인코딩 케이스 대비 (cp949)
        meeting_text = raw.decode("cp949", errors="replace")

    vm = build_viewmodel_from_meeting_text(
        meeting_text=meeting_text,
        meeting_name=file.filename or "meeting",
        topn=topn,
        mode=mode,
        evidence_mode=evidence,
    )
    ideas, dropped = parse_meeting_text_with_dropped(meeting_text, min_len=3, min_title_len=2)

    vm["parse"] = {
        "ideas_count": len(ideas),
        "dropped_count": len(dropped),
        "dropped": [{"raw": d.raw, "reason": d.reason} for d in dropped][:50],
        "policy": {"min_len": 3, "min_title_len": 2},
    }

    # FastAPI는 dict를 그냥 return 하면 JSON으로 자동 변환함
    return vm