from __future__ import annotations
import json
from pathlib import Path
import streamlit as st

REPORT_PATH = Path("data/reports/idea_cards.json")


def load_cards():
    if not REPORT_PATH.exists():
        st.error("idea_cards.json이 없습니다. 먼저 python -m app.main 실행하세요.")
        st.stop()
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def fmt_pct(x):
    try:
        return f"{float(x) * 100:.0f}%"
    except Exception:
        return "-"


st.set_page_config(page_title="Idea Decision Dashboard", layout="wide")
st.title("🚀 Startup Idea Decision Dashboard")

cards = load_cards()

# ---------------- Sidebar Filters ----------------
st.sidebar.header("Filters")
min_conf = st.sidebar.slider("Min Confidence", 0.0, 1.0, 0.2, 0.05)
min_priority = st.sidebar.slider("Min Priority", 0.0, 1.0, 0.2, 0.05)

filtered = [
    c for c in cards
    if c["scores"]["confidence"] >= min_conf
    and c["scores"]["priority"] >= min_priority
]

# ---------------- Ranking Table ----------------
st.subheader("📌 Ranking")

rows = []
for c in filtered:
    s = c["scores"]
    rows.append({
        "Title": c["title"],
        "Priority": fmt_pct(s["priority"]),
        "Feasibility": fmt_pct(s["feasibility"]),
        "Evidence": fmt_pct(s["evidence"]),
        "Momentum": fmt_pct(s["momentum"]),
        "Novelty": fmt_pct(s["novelty"]),
        "Confidence": fmt_pct(s["confidence"]),
        "Tags": ", ".join(c.get("tags", [])[:5]),
        "RawPriority": fmt_pct(s.get("raw_priority", s["priority"])),
    })

st.dataframe(rows, use_container_width=True, height=420)
st.caption(f"Total cards: {len(cards)} / Filtered: {len(filtered)}")

st.divider()

# ---------------- Detail View ----------------
st.subheader("🔍 Detail")

titles = [c["title"] for c in filtered]
if not titles:
    st.warning("필터 조건에 맞는 아이디어가 없습니다.")
    st.stop()

selected_title = st.selectbox("Select an idea", titles)
selected = next(c for c in filtered if c["title"] == selected_title)

col1, col2 = st.columns([1, 1])

with col1:
    st.markdown(f"## {selected['title']}")
    st.write(selected.get("summary", ""))

    st.markdown("### Scores")
    st.json(selected["scores"], expanded=False)

    st.markdown("### Drivers")
    st.write(selected.get("drivers", []))

    st.markdown("### Risks")
    st.write(selected.get("risks", []))

with col2:
    st.markdown("### Evidence")
    ev = selected.get("evidence", [])
    if ev:
        for e in ev[:10]:
            st.markdown(
                f"- **{e.get('title','')}** "
                f"({e.get('source','')}) · rel={e.get('relevance',0):.2f}"
            )
    else:
        st.info("No evidence")

    st.markdown("### Trend")
    st.json(selected.get("trend", {}), expanded=False)

st.divider()

# ---------------- Compare ----------------
st.subheader("🆚 Compare")

compare_titles = st.multiselect(
    "Pick ideas to compare",
    titles,
    default=titles[:2] if len(titles) >= 2 else []
)

if compare_titles:
    comp = []
    for c in filtered:
        if c["title"] in compare_titles:
            s = c["scores"]
            comp.append({
                "Title": c["title"],
                "Priority": fmt_pct(s["priority"]),
                "Feasibility": fmt_pct(s["feasibility"]),
                "Evidence": fmt_pct(s["evidence"]),
                "Momentum": fmt_pct(s["momentum"]),
                "Novelty": fmt_pct(s["novelty"]),
                "Confidence": fmt_pct(s["confidence"]),
            })

    st.dataframe(comp, use_container_width=True)