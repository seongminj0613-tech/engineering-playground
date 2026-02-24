from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from datetime import datetime
import re

from app.ingestion.meeting_input import load_meeting_text
from app.ingestion.meeting_parse import parse_meeting_text

# ✅ 너 프로젝트에 이미 있는 것들(대부분 네 코드에서 보였던 import들)
from app.matching.match_external import load_external_docs, match_evidence_for_idea, compute_market_signal
from app.scoring.model_v0_1 import ScoreModelV01
from app.scoring.signals import build_corpus_counter, extract_signals


ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "reports" / "meeting"
DOCS_MEETING_DIR = ROOT / "docs" / "meeting"


def enrich_signals_from_text(idea: dict, signals_kv: dict) -> dict:
    title = (idea.get("title") or "").strip()
    summary = (idea.get("summary") or "").strip()
    raw = (idea.get("raw_meeting") or "").strip()
    text = f"{title}\n{summary}\n{raw}".lower()

    # 토큰 수
    tokens = [w for w in re.split(r"\W+", text) if w]
    word_cnt = len(tokens)

    # 1) specificity: 연속 스케일 (0.20 ~ 0.90)
    # 길이 차이가 곧바로 점수 차이로 반영되게
    spec = min(0.90, max(0.20, word_cnt / 90.0))  # 90 단어면 1.0에 가까움
    signals_kv["specificity"] = max(float(signals_kv.get("specificity", 0.0)), spec)

    # 키워드 그룹
    novelty_kw = ["agent", "rag", "llm", "ai", "자동", "요약", "분석", "대시보드", "봇", "워크플로", "pipeline"]
    market_kw  = ["비용", "절감", "효율", "자동", "devops", "finops", "업무", "시간", "생산성", "고객", "구독"]
    hard_kw    = ["saas", "결제", "테넌트", "권한", "보안", "개인정보", "규제", "감사"]
    easy_kw    = ["대시보드", "리포트", "자동화", "봇", "정리", "분류", "알림", "요약"]

    # hit 수
    novelty_hit = sum(1 for k in novelty_kw if k in text)
    market_hit  = sum(1 for k in market_kw if k in text)
    hard_hit    = sum(1 for k in hard_kw if k in text)
    easy_hit    = sum(1 for k in easy_kw if k in text)

    # 2) novelty: hit 수 기반으로 더 크게 벌리기 (0.25 ~ 0.95)
    nov = 0.25 + (novelty_hit * 0.07) + (signals_kv.get("trend_boost", 0.0) * 0.10)
    signals_kv["novelty"] = min(0.95, max(float(signals_kv.get("novelty", 0.0)), nov))

    # 3) market_pull: 시장/업무효율 키워드 hit 수로 벌리기 (0.25 ~ 0.95)
    mp = 0.25 + (market_hit * 0.06)
    signals_kv["market_pull"] = min(0.95, max(float(signals_kv.get("market_pull", 0.0)), mp))

    # 4) feasibility: 쉬움(easy) - 어려움(hard)로 조정 (0.15 ~ 0.90)
    f0 = float(signals_kv.get("feasibility", 0.45))
    f  = f0 + (easy_hit * 0.05) - (hard_hit * 0.07)
    signals_kv["feasibility"] = min(0.90, max(0.15, f))

    # 5) clarity: 제목/요약 길이로 약간 차등
    # 너무 짧으면 낮게, 적당하면 높게
    c0 = float(signals_kv.get("clarity", 0.55))
    if len(title) >= 12:
        c0 += 0.05
    if len(summary) >= 40:
        c0 += 0.05
    signals_kv["clarity"] = min(0.90, max(0.20, c0))

    return signals_kv

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)
    


def _try_call(fn, *argsets):
    """
    함수 시그니처가 약간 달라도 실행되게 여러 패턴을 시도.
    argsets: [(args, kwargs), ...]
    """
    last = None
    for args, kwargs in argsets:
        try:
            return fn(*args, **kwargs)
        except TypeError as e:
            last = e
            continue
    raise last or RuntimeError("call failed")

def normalize_signals(sig_raw):
    """
    ScoreModelV01이 기대하는 형태로 강제 변환:
    - 최종 반환: (signals_list, signals_kv)
      signals_list: list[dict]  -> scorer.total_score에 넣는 용도
      signals_kv:   dict        -> HTML pill 표시용
    """
    # 1) JSON 문자열이면 파싱 시도
    if isinstance(sig_raw, str):
        s = sig_raw.strip()
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try:
                sig_raw = json.loads(s)
            except Exception:
                # 그냥 문자열이면 단일 시그널로 취급
                return ([{"type": "text_signal", "score": 1.0, "raw": sig_raw}], {"text_signal": 1.0})

        else:
            return ([{"type": "text_signal", "score": 1.0, "raw": sig_raw}], {"text_signal": 1.0})

    # 2) dict 형태면 -> list[dict]로 변환 (키=type, 값=score)
    if isinstance(sig_raw, dict):
        kv = {}
        lst = []
        for k, v in sig_raw.items():
            # 숫자만 score로 쓰고 나머진 설명용으로 kv에만
            try:
                fv = float(v)
                kv[k] = fv
                lst.append({"type": str(k), "score": fv})
            except Exception:
                # 숫자가 아니면 kv에 문자열로만 보관
                kv[str(k)] = v
        if not lst:
            lst = [{"type": "unknown", "score": 0.0}]
        return (lst, kv)

    # 3) list 형태면
    if isinstance(sig_raw, list):
        # list[dict]면 그대로 사용
        if sig_raw and isinstance(sig_raw[0], dict):
            kv = {}
            for d in sig_raw:
                t = (d.get("type") or "unknown")
                sc = d.get("score")
                if isinstance(sc, (int, float)):
                    kv[t] = float(sc)
            return (sig_raw, kv)

        # list[str]면 각 항목을 1점짜리 시그널로
        if sig_raw and isinstance(sig_raw[0], str):
            lst = [{"type": x, "score": 1.0} for x in sig_raw]
            kv = {x: 1.0 for x in sig_raw}
            return (lst, kv)

    # 4) 그 외 타입은 fallback
    return ([{"type": "unknown", "score": 0.0}], {"unknown": 0.0})
  
def coerce_total_score(x):
    """
    ScoreModelV01.total_score() 반환이
    - float/int 면 그대로
    - dict면 (total_score|total|score) 키를 우선 탐색해서 숫자를 뽑는다
    - 그래도 없으면 0.0
    """
    if isinstance(x, (int, float)):
        return float(x)

    if isinstance(x, dict):
        for k in ("total_score", "total", "score", "value"):
            v = x.get(k)
            if isinstance(v, (int, float)):
                return float(v)
            # 문자열 숫자도 허용
            try:
                return float(v)
            except Exception:
                pass
        # dict에 숫자가 아예 없으면 0
        return 0.0

    # 문자열 숫자 처리
    try:
        return float(x)
    except Exception:
        return 0.0

def _render_meeting_html(out_path: Path, title: str, top_items: list[dict]) -> None:
    # ✅ JSON을 HTML 안에 안전하게 넣기 위해 </script> 방지
    items_json = json.dumps(top_items, ensure_ascii=False).replace("</", "<\\/")

    html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title}</title>
<style>
body {{ margin:0; font-family: ui-sans-serif; background:#0b0f17; color:#e8eefc; }}
.wrap {{ display:grid; grid-template-columns: 1.2fr 0.8fr; gap:14px; padding:16px; max-width: 1200px; margin: 0 auto; }}
.card {{ padding:14px; border-radius:16px; background: rgba(255,255,255,0.06); }}
.list {{ display:flex; flex-direction:column; gap:8px; }}
.item {{ cursor:pointer; padding:10px; border-radius:12px; background: rgba(255,255,255,0.04); }}
.rank {{ font-weight:900; margin-right:6px; }}
.score {{ opacity:0.85; font-size:12px; }}
.pill {{ padding:4px 8px; border-radius:999px; background: rgba(157,193,255,0.12); font-size:12px; margin-right:6px; display:inline-block; margin-top:6px; }}
hr {{ border:0; border-top:1px solid rgba(255,255,255,0.10); margin:12px 0; }}
</style>
</head>
<body>

<div class="wrap">
  <div class="card" id="detail"></div>

  <div class="card">
    <div style="font-weight:900; margin-bottom:10px;">상용가능성 TOP</div>
    <div class="list" id="list"></div>
  </div>
</div>

<!-- ✅ 데이터를 JS코드가 아니라 JSON 스크립트로 안전하게 주입 -->
<script id="__DATA__" type="application/json">{items_json}</script>

<script>
function esc(s) {{
  return String(s ?? "")
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;");
}}

const items = (() => {{
  try {{
    const raw = document.getElementById("__DATA__")?.textContent || "[]";
    return JSON.parse(raw);
  }} catch (e) {{
    console.error("DATA PARSE ERROR", e);
    return [];
  }}
}})();

function renderDetail(i) {{
  const explainList = (i.explain_list || []).map(x =>
    `<div>• ${{esc(String(x).replaceAll("\\n"," ").replaceAll("\\r"," "))}}</div>`
  ).join("");

  const conf = (i.confidence != null) ? Number(i.confidence) : null;
  const confHtml = (conf != null)
    ? `<div style="margin-top:6px;">신뢰도: <b>${{esc(conf)}}</b></div>`
    : "";

  const ev = (i.evidence_top || i.evidence || []).map(e => {{
    const t = esc(e.title || "evidence");
    const u = e.url ? `<a href="${{esc(e.url)}} target="_blank">${{t}}</a>` : t;
    const src = esc(e.source || "");
    const sn = e.snippet
      ? `<div style="opacity:.8;font-size:12px;margin-left:10px;">${{esc(e.snippet)}}</div>`
      : "";
    return `<div>• ${{u}} (${{src}})${{sn}}</div>`;
  }}).join("");

  const sig = i.signals
    ? Object.entries(i.signals).slice(0,6).map(([k,v]) =>
      `<span class="pill">${{esc(k)}}: ${{esc(v)}}</span>`
    ).join("")
    : "";

  document.getElementById("detail").innerHTML = `
    <h2>#${{esc(i.rank)}} ${{esc(i.title)}}</h2>
    <div>총점: <b>${{esc(i.total_score)}}</b></div>
    ${{confHtml}}
    <div style="margin-top:8px;">${{explainList || esc(i.explain || "")}}</div>
    <div style="margin-top:10px;">${{sig}}</div>
    <div style="margin-top:10px;">${{esc(i.reason || "")}}</div>
    <hr>
    <div>${{ev || "증거 없음"}}</div>
  `;
}}

function renderList() {{
  const el = document.getElementById("list");
  if (!items.length) {{
    el.innerHTML = '<div style="opacity:.7;">결과가 비어있습니다.</div>';
    document.getElementById("detail").innerHTML = '<div style="opacity:.7;">결과가 비어있습니다.</div>';
    return;
  }}

  el.innerHTML = items.map((it, idx) => `
    <div class="item" onclick="renderDetail(items[${{idx}}])">
      <div><span class="rank">#${{esc(it.rank)}}</span>${{esc(it.title)}}</div>
      <div class="score">${{esc(it.total_score)}}</div>
    </div>
  `).join("");

  renderDetail(items[0]);
}}

renderList();
</script>

</body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")
    
def build_explain_list(signals_kv: dict) -> list[str]:
    out = []

    evc = signals_kv.get("evidence_count", 0)
    if evc:
        out.append(f"근거 {evc}건 기반 (외부/회의)")

    f = signals_kv.get("feasibility")
    if isinstance(f, (int, float)) and f >= 0.60:
        out.append("구현 난이도 현실적")

    mp = signals_kv.get("market_pull")
    if isinstance(mp, (int, float)) and mp >= 0.45:
        out.append("업무 효율/가치 신호 존재")

    nov = signals_kv.get("novelty")
    if isinstance(nov, (int, float)) and nov >= 0.55:
        out.append("차별성/신규성 확보")

    c = signals_kv.get("clarity")
    if isinstance(c, (int, float)) and c >= 0.65:
        out.append("요구사항이 비교적 명확")

    tb = signals_kv.get("trend_boost")
    if isinstance(tb, (int, float)) and tb >= 0.45:
        out.append("트렌드 상승 감지")

    if not out:
        out.append("회의 내 중요도 기반")
    return out

def extract_internal_evidence(idea: dict, top_k: int = 3) -> list[dict]:
    """
    external evidence가 0일 때, 회의 원문(raw_meeting)에서 관련 문장을 근거로 뽑는다.
    """
    title = (idea.get("title") or "").strip().lower()
    raw = (idea.get("raw_meeting") or "").strip()
    if not raw:
        return []

    kws = [w for w in re.split(r"\W+", title) if len(w) >= 2]
    kws = list(dict.fromkeys(kws))[:8]

    sents = [s.strip() for s in re.split(r"[.\n!?]+", raw) if s.strip()]
    scored = []
    for s in sents:
        low = s.lower()
        hit = sum(1 for w in kws if w in low)
        if hit > 0:
            scored.append((hit, s))

    scored.sort(key=lambda x: x[0], reverse=True)

    out = []
    for hit, s in scored[:top_k]:
        out.append({
            "source": "meeting",
            "title": f"회의 근거 (hit={hit})",
            "url": "",
            "snippet": s[:240],
            "published_at": "",
        })
    return out

def build_evidence_top(evidence) -> list[dict]:
    if not isinstance(evidence, list):
        return []
    ev = [e for e in evidence if isinstance(e, dict)]
    # title/url/snippet 위주로 3~5개만
    top = []
    for e in ev[:5]:
        top.append({
            "title": e.get("title") or e.get("headline") or "evidence",
            "url": e.get("url") or e.get("link") or "",
            "source": e.get("source") or e.get("publisher") or "external",
            "snippet": (e.get("snippet") or e.get("summary") or e.get("content") or "")[:240],
            "published_at": e.get("published_at") or e.get("date") or "",
        })
    return top

def _norm_score01(total_score: float) -> float:
    s = float(total_score or 0)

    # 이미 0~1 스케일이면 그대로
    if 0.0 <= s <= 1.5:
        return max(0.0, min(s, 1.0))

    # 0~100 스케일이면 정규화
    return max(0.0, min(s / 100.0, 1.0))

def calc_confidence(total_score: float, signals_kv: dict) -> float:
    evc = float(signals_kv.get("evidence_count", 0) or 0)
    feasibility = float(signals_kv.get("feasibility", 0) or 0)
    market_pull = float(signals_kv.get("market_pull", 0) or 0)
    clarity = float(signals_kv.get("clarity", 0) or 0)

    base = _norm_score01(total_score)  # ⭐ 핵심
    stability = (feasibility + market_pull + clarity) / 3.0

    ev_boost = min(evc * 0.08, 0.35)

    conf = base * 0.40 + stability * 0.45 + ev_boost
    return round(min(max(conf, 0.05), 0.99), 2)

def build_reason_explain(title, signals_kv, evidence):
    lines = []

    # evidence 기반
    evc = signals_kv.get("evidence_count", 0)
    if evc:
        lines.append(f"외부 근거 {evc}건 존재 → 시장 관심도 확인")

    # feasibility
    f = signals_kv.get("feasibility")
    if isinstance(f, (int, float)) and f >= 0.65:
        lines.append("기술 구현 난이도 현실적")

    # trend
    tb = signals_kv.get("trend_boost")
    if isinstance(tb, (int, float)) and tb >= 0.5:
        lines.append("최근 트렌드 상승 감지")

    if not lines:
        lines.append("회의 내부 중요도 높음")

    return " / ".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meeting", required=True, help="meeting file path (.txt/.md for beta)")
    ap.add_argument("--topn", type=int, default=10)
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    ap.add_argument("--external", default=str(ROOT / "data" / "external" / "external_docs.jsonl"))
    args = ap.parse_args()

    started = time.time()

    run_date = args.date or datetime.now().strftime("%Y-%m-%d")
    meeting_path = Path(args.meeting)
    meeting_id = meeting_path.stem

    # 1) load meeting text
    meeting_text = load_meeting_text(meeting_path)

    # 2) parse ideas from meeting
    meeting_ideas = parse_meeting_text(meeting_text)
    if not meeting_ideas:
        raise RuntimeError("No ideas parsed from meeting text. (Try adding bullets or '아이디어: ...')")

    # 3) load evidence corpus
    external_path = Path(args.external)
    external_docs = load_external_docs(external_path)

    corpus_counter = build_corpus_counter(external_docs)
    scorer = ScoreModelV01({})  # cfg는 나중에 configs/scoring.yml로 연결

    scored_items: list[dict] = []

    for idx, it in enumerate(meeting_ideas, start=1):
        idea = {
            "idea_id": f"MEET-{meeting_id}-{idx:03d}",
            "title": it.title,
            "summary": f"{it.title}\n{it.reason}".strip(),
            "raw_meeting": it.raw,
            "source": "meeting",
        }

        # evidence match
        evidence = _try_call(
            match_evidence_for_idea,
            ((idea, external_docs), {}),
            ((idea, external_docs), {"top_k": 5}),
            ((idea, external_docs), {"k": 5}),
        )
        try:
            title_tokens = [w.strip().lower() for w in it.title.split() if len(w.strip()) >= 2]
            extra = []

            for d in external_docs[:400]:
                blob = f"{d.get('title','')} {d.get('summary','')} {d.get('content','')}".lower()
                hit = sum(1 for w in title_tokens if w in blob)
                if hit >= 2:
                   extra.append({
                       "source": d.get("source") or d.get("publisher") or "external",
                       "title": d.get("title") or d.get("headline") or "evidence",
                       "url": d.get("url") or d.get("link") or "",
                       "snippet": (d.get("summary") or d.get("content") or "")[:240],
                       "published_at": d.get("published_at") or d.get("date") or "",
                  })

            if extra:
                if isinstance(evidence, list):
                    seen = set((e.get("title") or "").lower() for e in evidence if isinstance(e, dict))
                    for e in extra:
                        t = (e.get("title") or "").lower()
                        if t and t not in seen:
                           evidence.append(e)
                           seen.add(t)
                if len(evidence) >= 8:
                    evidence = evidence[:8]
            else:
                evidence = extra[:5]
        except Exception:
            pass
        
        if not isinstance(evidence, list):
            evidence = []
        if len(evidence) == 0:
            evidence = extract_internal_evidence(idea, top_k=3)
        
        external_evidence_items = evidence if isinstance(evidence, list) else []

        # market signal (지금은 옵션)
        try:
            market_signal = compute_market_signal(idea)
        except Exception:
            market_signal = {}

        # signals (여기서 signals_kv 생성됨!)
        sig_raw = _try_call(
            extract_signals,
            ((idea,), {}),
            ((idea, corpus_counter), {}),
            ((idea, corpus_counter, evidence), {}),
            ((idea, corpus_counter, evidence, market_signal), {}),
            ((idea,), {"corpus_counter": corpus_counter}),
            ((idea,), {"corpus_counter": corpus_counter, "evidence": evidence}),
            ((idea,), {"corpus_counter": corpus_counter, "evidence": evidence, "market_signal": market_signal}),
        )
        signals_list, signals_kv = normalize_signals(sig_raw)

        # ✅ evidence_count는 여기서만!
        signals_kv["evidence_count"] = len(evidence) if isinstance(evidence, list) else int(bool(evidence))
        signals_list.append({"type": "evidence_count", "score": float(signals_kv["evidence_count"])})

        # scoring
        total_raw = scorer.total_score(idea, signals_list)
        total_score = coerce_total_score(total_raw)
        
        explain_list = build_explain_list(signals_kv)
        evidence_top = build_evidence_top(evidence)
        confidence = calc_confidence(total_score, signals_kv)

        scored_items.append({
             "idea_id": idea["idea_id"],
             "title": it.title,
             "reason": it.reason,
             "raw": it.raw,
             "signals": signals_kv,
             "total_score": round(total_score, 2),
             "score_detail": total_raw if isinstance(total_raw, dict) else None,
             "evidence": evidence,
             "evidence_top": evidence_top,
             "explain": build_reason_explain(it.title, signals_kv, evidence),
             "explain_list": explain_list,
             "confidence": confidence,
        })

    # 4) sort + rank + topn
    scored_items.sort(key=lambda r: float(r.get("total_score", 0) or 0), reverse=True)
    top = scored_items[: max(1, args.topn)]
    for i, r in enumerate(top, start=1):
        r["rank"] = i

    elapsed_ms = int((time.time() - started) * 1000)

    # 5) save outputs
    out_report_dir = REPORTS_DIR / run_date
    out_html_dir = DOCS_MEETING_DIR / run_date
    _ensure_dir(out_report_dir)
    _ensure_dir(out_html_dir)

    report_path = out_report_dir / f"{meeting_id}.json"
    html_path = out_html_dir / f"{meeting_id}.html"

    report = {
        "run_id": f"MR-{run_date}-{meeting_id}",
        "meeting": {"id": meeting_id, "date": run_date, "source_path": str(meeting_path)},
        "stats": {
            "ideas_found": len(meeting_ideas),
            "ideas_scored": len(scored_items),
            "topn": len(top),
            "elapsed_ms": elapsed_ms,
        },
        "top": top,
        "artifacts": {
            "report_json": str(report_path),
            "html": str(html_path),
        },
    }

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _render_meeting_html(html_path, title=f"{meeting_id} ({run_date})", top_items=top)

    print(f"✅ MeetingRun done: {report_path}")
    print(f"✅ HTML rendered: {html_path}")
    
def run_meeting_analysis_from_text(
    meeting_text: str,
    meeting_id: str = "uploaded_meeting",
    run_date: str | None = None,
    topn: int = 10,
    external_path: str | None = None,
    evidence_mode: str = "none",  # "none" | "external"    
) -> dict:
    """
    FastAPI에서 호출하는 '엔진 함수'
    - report(dict) 형태로 반환 (기존 report.json 구조와 유사)
    - 파일 저장/HTML 렌더는 옵션으로 분리 가능
    """

    started = time.time()
    run_date = run_date or datetime.now().strftime("%Y-%m-%d")

    # 1) parse ideas from meeting
    meeting_ideas = parse_meeting_text(meeting_text)
    if not meeting_ideas:
        raise RuntimeError("No ideas parsed from meeting text. (Try adding bullets or '아이디어: ...')")

    # 2) evidence corpus (옵션)
    external_docs = []
    corpus_counter = None

    if evidence_mode == "external":
        if not external_path:
            external_path = str(ROOT / "data" / "external" / "external_docs.jsonl")
        external_docs = load_external_docs(Path(external_path))
        corpus_counter = build_corpus_counter(external_docs)

    scorer = ScoreModelV01({})

    scored_items: list[dict] = []

    for idx, it in enumerate(meeting_ideas, start=1):
        idea = {
            "idea_id": f"MEET-{meeting_id}-{idx:03d}",
            "title": it.title,
            "summary": f"{it.title}\n{it.reason}".strip(),
            "raw_meeting": it.raw,
            "source": "meeting",
        }

        # evidence match (옵션)
        evidence = []
        if evidence_mode == "external" and external_docs:
            evidence = _try_call(
                match_evidence_for_idea,
                ((idea, external_docs), {}),
                ((idea, external_docs), {"top_k": 5}),
                ((idea, external_docs), {"k": 5}),
            )
            # 네가 만든 extra evidence 보강 로직도 여기 붙여도 됨(그대로 복붙 OK)
        
        if not isinstance(evidence, list):
            evidence = []
        if len(evidence) == 0:
            evidence = extract_internal_evidence(idea, top_k=3)

        if isinstance(evidence, list):
           evidence = [e for e in evidence if isinstance(e, dict)]
        else:
           evidence = []

        external_evidence_items = evidence[:8]

        # market signal (옵션) - 필요하면 external 모드일 때만 돌려도 됨
        try:
            market_signal = compute_market_signal(idea)
        except Exception:
            market_signal = {}

        # signals
        sig_raw = _try_call(
            extract_signals,
            ((idea,), {}),
            ((idea, corpus_counter), {}),
            ((idea, corpus_counter, evidence), {}),
            ((idea, corpus_counter, evidence, market_signal), {}),
            ((idea,), {"corpus_counter": corpus_counter}),
            ((idea,), {"corpus_counter": corpus_counter, "evidence": evidence}),
            ((idea,), {"corpus_counter": corpus_counter, "evidence": evidence, "market_signal": market_signal}),
        )
        signals_list, signals_kv = normalize_signals(sig_raw)
        
        signals_kv = enrich_signals_from_text(idea, signals_kv)

        # signals_list 재구성 (스코어 계산용)
        signals_list = [
            {"type": k, "score": float(v)}
            for k, v in signals_kv.items()
            if isinstance(v, (int, float))
        ]

        # evidence_count는 external 모드에서만 의미 있게
        ev_count = len(evidence) if isinstance(evidence, list) else int(bool(evidence))
        signals_kv["evidence_count"] = ev_count
        signals_list.append({"type": "evidence_count", "score": float(ev_count)})

        # scoring
        total_raw = scorer.total_score(idea, signals_list)
        total_score = coerce_total_score(total_raw)
        explain_list = build_explain_list(signals_kv)
        evidence_top = build_evidence_top(evidence)
        confidence = calc_confidence(total_score, signals_kv)

        scored_items.append({
            "idea_id": idea["idea_id"],
            "title": it.title,
            "summary": f"{it.title}\n{it.reason}".strip(),         # ✅ API/앱용으로 summary 키로 정리
            "raw": it.raw,
            "signals": signals_kv,           # dict
            "total_score": float(total_score),# ✅ 0~? (너 모델 스케일 그대로)
            "score_detail": total_raw if isinstance(total_raw, dict) else None,
            "evidence": evidence,
            "explain": build_reason_explain(it.title, signals_kv, evidence),
            "external_evidence_items": external_evidence_items,
            "evidence_top": evidence_top,
            "explain_list": explain_list, 
            "confidence": confidence,
        })

    # 4) sort + rank + topn
    scored_items.sort(key=lambda r: float(r.get("total_score", 0) or 0), reverse=True)
    top = scored_items[: max(1, topn)]
    for i, r in enumerate(top, start=1):
        r["rank"] = i

    elapsed_ms = int((time.time() - started) * 1000)

    report = {
        "run_id": f"MR-{run_date}-{meeting_id}",
        "meeting": {"id": meeting_id, "date": run_date},
        "stats": {
            "ideas_found": len(meeting_ideas),
            "ideas_scored": len(scored_items),
            "topn": len(top),
            "elapsed_ms": elapsed_ms,
            "evidence_mode": evidence_mode,
        },
        "top": top,
    }
    return report


if __name__ == "__main__":
    main()