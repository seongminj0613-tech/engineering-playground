import csv
import re
import time
import requests
import os
from datetime import datetime, timezone
from urllib.parse import urlencode
from collections import Counter, defaultdict
from contextlib import redirect_stdout

ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search"
ALGOLIA_ITEM = "https://hn.algolia.com/api/v1/items"  # items/<id> 로 댓글 트리 조회

# 회의/콜 요약 (사후 업로드) 관련 검색어
QUERIES = [
    "meeting summary",
    "meeting notes",
    "meeting minutes",
    "call summary",
    "sales call recap",
    "action items meeting",
    "transcript summarization",
    "audio transcription meeting",
    "notes to action items",
    "AI meeting assistant"
]

MAX_RESULTS = 30
HITS_PER_QUERY = 20
COMMENT_TEXT_LIMIT = 12000  # 너무 길면 잘라서 태깅 (속도/안정)
REQUEST_SLEEP_SEC = 0.15     # HN API 과도호출 방지

# 패턴 추정 (초기 휴리스틱)
PATTERN_RULES = {
    "Hybrid/RAG": re.compile(r"\b(rag|retriev|vector|embedding|pinecone|qdrant|faiss)\b", re.I),
    "Agent": re.compile(r"\b(agent|tool calling|function calling|workflow|planner|executor)\b", re.I),
}

# 회의/콜 요약 Core AI 기능 태그(강화 버전)
FEATURE_RULES = {
    "timestamp_alignment": re.compile(r"\b(timestamp|timecode|hh:mm:ss|mm:ss)\b", re.I),
    "action_items": re.compile(r"\b(action item|action-items|todo|to-do|next steps|follow[- ]?up)\b", re.I),
    "speaker_labels": re.compile(r"\b(diarization|speaker label|speaker separation|speaker)\b", re.I),
    "structured_output": re.compile(r"\b(json|schema|structured output|structured)\b", re.I),
    "hallucination_guard": re.compile(r"\b(grounded|citation|cite|don['’]t make up|factual|verbatim)\b", re.I),
    "multilingual": re.compile(r"\b(multilingual|korean|japanese|english|spanish|translate|translation)\b", re.I),
    "pii_redaction": re.compile(r"\b(pii|redact|redaction|privacy|gdpr|hipaa)\b", re.I),
    "meeting_memory": re.compile(r"\b(memory|project context|context from previous)\b", re.I),
    "glossary_style": re.compile(r"\b(glossary|style guide|terminology|jargon)\b", re.I),
}

# 리스크 키워드 (후기/댓글에서 자주 나오는 것)
RISK_RULES = {
    "cost_explosion": re.compile(r"\b(cost|expensive|tokens|billing|price)\b", re.I),
    "latency": re.compile(r"\b(latency|slow|delay)\b", re.I),
    "hallucination": re.compile(r"\b(hallucinat|made up|incorrect|wrong)\b", re.I),
    "privacy": re.compile(r"\b(privacy|pii|gdpr|hipaa|confidential)\b", re.I),
}

def fetch_search(query: str, hits_per_page: int = 20):
    params = {"query": query, "tags": "story", "hitsPerPage": hits_per_page}
    url = f"{ALGOLIA_SEARCH}?{urlencode(params)}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    time.sleep(REQUEST_SLEEP_SEC)
    return r.json().get("hits", [])

def fetch_item_tree(object_id: str) -> dict:
    # 댓글 포함 트리 조회
    url = f"{ALGOLIA_ITEM}/{object_id}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    time.sleep(REQUEST_SLEEP_SEC)
    return r.json()

def collect_comments_text(node: dict, acc: list, depth: int = 0, max_depth: int = 6):
    if depth > max_depth:
        return
    text = node.get("text")
    if text:
        # HTML 태그 아주 대충 제거(완전 정교할 필요 없음)
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        if clean:
            acc.append(clean)
    for child in node.get("children", []) or []:
        collect_comments_text(child, acc, depth + 1, max_depth=max_depth)

def infer_pattern(text: str) -> str:
    for name, rx in PATTERN_RULES.items():
        if rx.search(text):
            return name
    return "Generator(Prompt-only)"

def infer_features(text: str):
    feats = [k for k, rx in FEATURE_RULES.items() if rx.search(text)]
    return feats[:10]

def infer_risks(text: str):
    risks = [k for k, rx in RISK_RULES.items() if rx.search(text)]
    return risks[:10]

def safe_date(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d")
    except Exception:
        return datetime.min
    
def collect_cases():
    seen = set()
    cases = []

    # --- A) 케이스 수집 + 댓글 텍스트 결합 ---
    for q in QUERIES:
        for hit in fetch_search(q, hits_per_page=HITS_PER_QUERY):
            obj_id = hit.get("objectID")
            if not obj_id or obj_id in seen:
                continue
            seen.add(obj_id)

            title = hit.get("title") or ""
            author = hit.get("author") or ""
            points = hit.get("points") or 0
            comments = hit.get("num_comments") or 0
            created_at = hit.get("created_at") or ""
            created_date = created_at.split("T")[0] if "T" in created_at else created_at

            url = hit.get("url") or f"https://news.ycombinator.com/item?id={obj_id}"

            # 댓글 트리 가져오기
            comment_texts = []
            try:
                tree = fetch_item_tree(obj_id)
                collect_comments_text(tree, comment_texts)
            except Exception:
                comment_texts = []

            comments_blob = " ".join(comment_texts)
            if len(comments_blob) > COMMENT_TEXT_LIMIT:
                comments_blob = comments_blob[:COMMENT_TEXT_LIMIT]

            blob = f"{title} {hit.get('story_text') or ''} {comments_blob} {url}"
            pattern = infer_pattern(blob)
            features = infer_features(blob)
            risks = infer_risks(blob)

            cases.append({
                "object_id": obj_id,
                "date": created_date,
                "title": title[:140],
                "url": url,
                "author": author,
                "points": points,
                "comments": comments,
                "pattern": pattern,
                "core_ai_features": ",".join(features) if features else "-",
                "risks": ",".join(risks) if risks else "-"
            })

            if len(cases) >= MAX_RESULTS:
                break
        if len(cases) >= MAX_RESULTS:
            break

    cases.sort(key=lambda r: safe_date(r["date"]), reverse=True)

    # --- 출력 ---
    print("\n=== HN Meeting/Call Summary Cases (Top) - with Comments ===")
    for i, r in enumerate(cases, 1):
        print(f"\n[{i}] {r['date']} | {r['pattern']} | pts:{r['points']} com:{r['comments']}")
        print(f"    {r['title']}")
        print(f"    features: {r['core_ai_features']}")
        print(f"    risks:    {r['risks']}")
        print(f"    url: {r['url']}")

    # --- 저장 1) 케이스 CSV ---
    out_cases = "hn_meeting_summary_cases.csv"
    with open(out_cases, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cases[0].keys()) if cases else [
            "date","title","url","author","points","comments","pattern","core_ai_features","risks"
        ])
        w.writeheader()
        w.writerows(cases)
    print(f"\nSaved: {out_cases}")
    print(">>> STEP B START (graph edges)")

    # --- B) 그래프 엣지 스냅샷 ---
    edge_counter = Counter()

    def add_edge(frm, rel, to):
        edge_counter[(frm, rel, to)] += 1

    for c in cases:
        case_id = f"case_{c['object_id']}"
        pattern = c["pattern"]
        add_edge(case_id, "has_pattern", pattern)

        feats = [] if c["core_ai_features"] == "-" else c["core_ai_features"].split(",")
        for ft in feats:
            add_edge(pattern, "uses_feature", ft)
            add_edge(case_id, "mentions_feature", ft)

        rks = [] if c["risks"] == "-" else c["risks"].split(",")
        for rk in rks:
            add_edge(pattern, "has_risk_signal", rk)
            add_edge(case_id, "mentions_risk", rk)

    out_edges = "graph_edges_snapshot.csv"
    today = datetime.now().strftime("%Y-%m-%d")
    with open(out_edges, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date","from","relation","to","weight"])
        w.writeheader()
        for (frm, rel, to), wgt in edge_counter.most_common():
            w.writerow({"date": today, "from": frm, "relation": rel, "to": to, "weight": wgt})
    print(f"Saved: {out_edges}")
    print(">>> STEP C START (daily metrics)")

    # --- C) daily metrics ---
    mentions = len(cases)
    total_points = sum(c["points"] for c in cases)
    total_comments = sum(c["comments"] for c in cases)

    pattern_counts = Counter(c["pattern"] for c in cases)
    def share(name):
        return round(pattern_counts.get(name, 0) / mentions, 4) if mentions else 0

    all_feats, all_risks = [], []
    for c in cases:
        if c["core_ai_features"] != "-":
            all_feats += c["core_ai_features"].split(",")
        if c["risks"] != "-":
            all_risks += c["risks"].split(",")

    top_feat = Counter(all_feats).most_common(1)
    top_risk = Counter(all_risks).most_common(1)

    interest_score = total_points + (2 * total_comments) + (5 * mentions)

    out_daily = "daily_interest_metrics.csv"
    row = {
        "date": today,
        "usecase": "meeting_call_summary_post_upload",
        "mentions": mentions,
        "total_points": total_points,
        "total_comments": total_comments,
        "interest_score": interest_score,
        "share_generator": share("Generator(Prompt-only)"),
        "share_hybrid_rag": share("Hybrid/RAG"),
        "share_agent": share("Agent"),
        "top_feature": top_feat[0][0] if top_feat else "-",
        "top_risk": top_risk[0][0] if top_risk else "-",
    }

    exists = os.path.exists(out_daily)

   

    print(f"Saved: {out_daily}")
    print("=== Daily Metrics ===")
    print(row)

    return cases
from collections import Counter

def _split_list(s):
    if not s or s == "-":
        return []
    return [x.strip() for x in s.split(",") if x.strip()]

def _clamp01(x: float) -> float:
    if x < 0: return 0.0
    if x > 1: return 1.0
    return x

def print_decision_brief(cases):
    print("\n\n🔥 DECISION BRIEF CALLED 🔥\n")
    if not cases:
        print("\n=== Reference Decision Brief ===\n(no cases)")
        return

    mentions = len(cases)
    pattern_counts = Counter(c["pattern"] for c in cases)
    dominant_pattern, dom_cnt = pattern_counts.most_common(1)[0]
    dom_share = dom_cnt / mentions

    feat_counts = Counter()
    risk_counts = Counter()
    for c in cases:
        feat_counts.update(_split_list(c.get("core_ai_features", "-")))
        risk_counts.update(_split_list(c.get("risks", "-")))

    top_feats = feat_counts.most_common(8)
    top_risks = risk_counts.most_common(5)

    total_points = sum(int(c.get("points", 0) or 0) for c in cases)
    total_comments = sum(int(c.get("comments", 0) or 0) for c in cases)

    confidence = (
        0.55 * dom_share +
        0.25 * _clamp01(mentions / 10) +
        0.20 * _clamp01((total_points + total_comments) / 200)
    )
    confidence_label = "High" if confidence >= 0.75 else ("Medium" if confidence >= 0.5 else "Low")

    decision_why = {
        "Generator(Prompt-only)": [
            "시장 시그널 기준으로 가장 흔한 출발점(구현 난이도 낮음)",
            "Team/SMB에 맞는 빠른 출시/반복(피드백 루프) 가능",
            "비용/운영 복잡도가 비교적 낮아 PoC→유료전환이 쉬움",
        ],
        "Hybrid/RAG": [
            "도메인 지식/내부 문서 결합이 핵심이면 RAG가 가치가 큼",
            "다만 인덱싱/품질/권한/데이터 신선도 운영 부담이 증가",
        ],
        "Agent": [
            "툴 실행/업무 자동화가 중심이면 Agent가 강력",
            "다만 예측 불가능성/안전장치/관측성 요구가 큼",
        ],
    }

    risk_playbook = {
        "hallucination": ["hallucination_guard", "human_review", "structured_output", "timestamp_alignment"],
        "privacy": ["pii_redaction", "access_control", "retention_policy", "audit_log"],
        "cost_explosion": ["batching", "chunking", "caching", "rate_limit"],
        "latency": ["queueing", "batching", "caching"],
    }

    checklist = {
        "Must (MVP to sell)": [
            "Upload UX (post-upload flow)",
            "Summary templates (meeting type presets)",
            "Editing & Approval (human-in-the-loop)",
            "Export/Share (Slack/Notion/email)",
            "Basic privacy controls (PII redaction + retention)",
        ],
        "Should (stickiness)": [
            "Action items + owners + due dates",
            "Timestamp jump-to-text/audio",
            "Multi-language output",
            "Integrations (Jira/Trello/CRM)",
        ],
        "Could (differentiators)": [
            "Project/meeting memory (team context)",
            "Glossary/style injection",
            "Speaker labels/diarization (if input supports)",
        ]
    }

    print("\n" + "="*72)
    print("REFERENCE DECISION BRIEF")
    print("Usecase: Meeting/Call Summary (Post-upload) | Target: Team/SMB")
    print("="*72)

    print("\n[Decision]")
    print(f"- Recommended Architecture: {dominant_pattern}")
    print(f"- Confidence: {confidence_label} ({confidence:.2f})")
    print(f"- Evidence: cases={mentions}, points={total_points}, comments={total_comments}")

    print("\n[Why this is the default]")
    for line in decision_why.get(dominant_pattern, ["(no template)"]):
        print(f"- {line}")

    print("\n[Market Signals]")
    print("- Pattern share:")
    for p, cnt in pattern_counts.most_common():
        print(f"  - {p}: {cnt}/{mentions} ({cnt/mentions:.2f})")

    print("\n[Build First: Core AI capabilities]")
    if top_feats:
        for k, v in top_feats[:6]:
            print(f"- {k} (signal={v})")
    else:
        print("- (no features detected — expand tagging rules / fetch linked pages)")

    print("\n[Top Risks & Mitigations]")
    if top_risks:
        for rk, v in top_risks:
            mitigations = risk_playbook.get(rk, ["(no playbook yet)"])
            print(f"- {rk} (signal={v}) → " + " + ".join(mitigations))
    else:
        print("- (no risks detected)")

    print("\n[Commercialization Checklist]")
    for section, items in checklist.items():
        print(f"- {section}:")
        for it in items:
            print(f"  - {it}")

    print("\n[Defer (avoid early complexity)]")
    if dominant_pattern == "Generator(Prompt-only)":
        print("- Full Agent orchestration (tool chains) — overkill for MVP")
        print("- Heavy RAG infra — 품질/운영 부담이 먼저 커짐")
        print("- 완전 자동 배포/실행형 워크플로우 — 안전장치 후순위")
    elif dominant_pattern == "Hybrid/RAG":
        print("- Agent-style autonomous actions without guardrails")
        print("- Broad indexing without access controls")
    else:
        print("- Autonomous tool execution without observability/audit")
        print("- Unbounded actions (no policy + no rate limits)")

    print("\n[Evidence Cases (top 5 by points)]")
    top_cases = sorted(cases, key=lambda x: int(x.get("points", 0) or 0), reverse=True)[:5]
    for c in top_cases:
        print(f"- pts:{c.get('points',0)} | {c.get('title','')[:95]}")
        print(f"  {c.get('url','')}")

    print("\n[Architecture Skeleton (ASCII)]")
    print(f"{dominant_pattern}")
    for req in ["structured_output", "action_items", "human_review_loop"]:
        print(f" ├─ requires → {req}")
    for imp in ["timestamp_alignment", "multilingual"]:
        print(f" ├─ improves → {imp}")
    if top_risks:
        rk0 = top_risks[0][0]
        mit0 = " + ".join(risk_playbook.get(rk0, ["(no playbook yet)"]))
        print(f" └─ risk → {rk0} (mitigate: {mit0})")
    else:
        print(" └─ risk → (none detected)")

    print("="*72)
    
def main():
    cases = run_pipeline()
    generate_mvp_report(cases)
    
def run_plot():
    import subprocess, sys
    subprocess.run([sys.executable, "plot_graph.py"], check=True)
    
def run_pipeline():
    cases = collect_cases()     # ✅ 수집 + csv 저장
    run_plot()                  # ✅ 그래프 생성
    return cases
def generate_mvp_report(cases):
    os.makedirs("reports", exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    report_path = f"reports/{today}_mvp_brief.txt"

    with open(report_path, "w", encoding="utf-8") as f:
        with redirect_stdout(f):
            print("==== MVP Reference Brief ====")
            print(f"date: {today}\n")
            print_decision_brief(cases)

            print("\n---- Artifacts ----")
            print("- graph_edges_snapshot.csv")
            print("- daily_interest_metrics.csv")
            print(f"- snapshots/reference_graph_{today}.png")

    print(f"📄 Report saved -> {report_path}")
    

if __name__ == "__main__":
    main()