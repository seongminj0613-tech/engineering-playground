from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]  # 프로젝트 루트
REPORT_PATH = ROOT / "data" / "reports" / "idea_cards.json"
SNAPSHOTS_DIR = ROOT / "snapshots"


def load_cards() -> list[dict]:
    if not REPORT_PATH.exists():
        return []
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def score_of(card: dict) -> float:
    s = card.get("scores") or {}
    try:
        return float(s.get("priority") or 0)
    except Exception:
        return 0.0


def latest_graph_image() -> Path | None:
    # 1) latest 우선
    p = SNAPSHOTS_DIR / "reference_graph_latest.png"
    if p.exists():
        return p

    # 2) 없으면 최신 png
    if not SNAPSHOTS_DIR.exists():
        return None
    pngs = sorted(SNAPSHOTS_DIR.glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True)
    return pngs[0] if pngs else None


st.set_page_config(page_title="Idea Decision Dashboard", layout="wide")

st.title("Idea Decision Dashboard")
st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.write(f"Cards source: `{REPORT_PATH}`")

cards = load_cards()

if not cards:
    st.warning("`idea_cards.json`이 없어요. 먼저 파이프라인을 돌려줘: `python -m app.main`")
    st.stop()

# Sidebar
st.sidebar.header("Filters")
top_n = st.sidebar.slider("Top N", 5, 50, 10)
min_priority = st.sidebar.slider("Min Priority", 0.0, 1.0, 0.0, 0.05)
q = st.sidebar.text_input("Search (title/summary/features/risks)", "")

# Filter + sort
filtered = []
for c in cards:
    pri = score_of(c)
    if pri < min_priority:
        continue

    title = (c.get("title") or c.get("idea") or "").lower()
    summary = (c.get("summary") or c.get("one_liner") or "").lower()
    features = c.get("features") or []
    risks = c.get("risks") or []

    hay = " ".join([
        title,
        summary,
        " ".join(features) if isinstance(features, list) else str(features),
        " ".join(risks) if isinstance(risks, list) else str(risks),
    ])

    if q.strip() and q.strip().lower() not in hay:
        continue

    filtered.append(c)

filtered = sorted(filtered, key=score_of, reverse=True)
top = filtered[:top_n]

colA, colB = st.columns([2, 1])

with colA:
    st.subheader("Top Cards")
    for i, c in enumerate(top, start=1):
        title = c.get("title") or c.get("idea") or f"idea_{i}"
        summary = c.get("summary") or c.get("one_liner") or ""
        url = c.get("url") or ""
        features = c.get("features") or []
        risks = c.get("risks") or []

        with st.expander(f"#{i} {title}  (priority={score_of(c):.2f})", expanded=(i <= 3)):
            if summary:
                st.write(summary)
            if url:
                st.write(url)
            st.write("**features**:", ", ".join(features) if isinstance(features, list) else str(features))
            st.write("**risks**:", ", ".join(risks) if isinstance(risks, list) else str(risks))
            st.json(c)

with colB:
    st.subheader("Latest Graph")
    img = latest_graph_image()
    if img:
        st.image(str(img), use_container_width=True)
        st.caption(str(img.relative_to(ROOT)))
    else:
        st.info("`snapshots/`에 그래프 이미지가 없어요.")

    st.subheader("Quick Commands")
    st.code("python -m app.main", language="bash")
    st.code("streamlit run app/ui/dashboard.py", language="bash")