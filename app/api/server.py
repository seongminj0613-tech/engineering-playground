from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uuid
import json
from fastapi.responses import RedirectResponse
# ✅ 너가 이미 만든 엔진 함수 import
from app.runs.meeting_run import run_meeting_analysis_from_text, _render_meeting_html


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"
MEETING_APP_DIR = DOCS_DIR / "meeting_app"
TMP_DIR = ROOT / "reports" / "_tmp_web"
TMP_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Meeting Decision Engine")

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/app/")

# 정적 페이지 제공: /app -> 업로드 UI
app.mount("/app", StaticFiles(directory=str(MEETING_APP_DIR), html=True), name="meeting_app")


@app.get("/", response_class=HTMLResponse)
def home():
    # / 로 접속하면 업로드 UI로 보내기
    index = (MEETING_APP_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(index)


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    evidence_mode: str = Form("external"),
):
    # 1) 파일 읽기
    raw = await file.read()
    try:
        meeting_text = raw.decode("utf-8")
    except UnicodeDecodeError:
        # 혹시 CP949로 들어오면 여기서 한 번 더
        meeting_text = raw.decode("cp949", errors="replace")

    meeting_id = Path(file.filename or "uploaded_meeting").stem
    run_id = uuid.uuid4().hex[:10]

    # 2) 엔진 실행
    report = run_meeting_analysis_from_text(
        meeting_text=meeting_text,
        meeting_id=f"{meeting_id}-{run_id}",
        evidence_mode=evidence_mode,   # "external" | "none"
    )

    # 3) 결과 HTML 생성해서 임시 저장
    html_path = TMP_DIR / f"{report['meeting']['id']}.html"
    _render_meeting_html(
        out_path=html_path,
        title=f"{report['meeting']['id']} ({report['meeting']['date']})",
        top_items=report["top"],
    )

    # 4) 결과 보기 URL 반환
    view_url = f"/view/{html_path.name}"
    return JSONResponse({
        "ok": True,
        "run_id": report["run_id"],
        "meeting_id": report["meeting"]["id"],
        "view_url": view_url,
        "stats": report["stats"],
    })


@app.get("/view/{name}", response_class=HTMLResponse)
def view_result(name: str):
    p = TMP_DIR / name
    if not p.exists():
        return HTMLResponse("<h3>결과 파일이 없음</h3>", status_code=404)
    return HTMLResponse(p.read_text(encoding="utf-8"))