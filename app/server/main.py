from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from app.server.viewmodel import build_viewmodel_from_meeting_text
from app.ingestion.meeting_parse import parse_meeting_text_with_dropped

import re
from app.explain.explain_layer import (
    build_evidence_trace,
    build_risk_analysis,
    build_next_actions,
    build_confidence,
)

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
    rows_key = None
    for k in ["items", "ranked", "rows", "top", "results"]:
        if k in vm and isinstance(vm[k], list) and (len(vm[k]) == 0 or isinstance(vm[k][0], dict)):
            rows_key = k
            break

    if rows_key:
        rows = vm[rows_key]
        for row in rows:
            # evidence_trace: 회의 원문 기반
            ev_trace = build_evidence_trace(meeting_text, row, max_items=3)
            row["evidence_trace"] = ev_trace

            # evidence_count 보정 (fallback 문장은 count로 안침)
            ev_count = int(row.get("evidence_count", 0) or 0)
            if ev_count == 0 and ev_trace and not ev_trace[0].startswith("회의 인용을 찾지 못함"):
                ev_count = len(ev_trace)
            row["evidence_count"] = ev_count

            # confidence 자동 계산
            row["confidence"] = build_confidence(row)

            # explain 생성
            row["explain"] = {
                "evidence_trace": ev_trace,
                "risk_analysis": build_risk_analysis(row),
                "next_actions": build_next_actions(row),
                "confidence": row["confidence"],
            }
            
    ideas, dropped = parse_meeting_text_with_dropped(meeting_text, min_len=3, min_title_len=2)

    vm["parse"] = {
        "ideas_count": len(ideas),
        "dropped_count": len(dropped),
        "dropped": [{"raw": d.raw, "reason": d.reason} for d in dropped][:50],
        "policy": {"min_len": 3, "min_title_len": 2},
    }

    # FastAPI는 dict를 그냥 return 하면 JSON으로 자동 변환함
    return vm