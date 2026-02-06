from pathlib import Path
from datetime import datetime


def render_md(report_dir: Path, context: dict):
    report_dir.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append(f"# Idea Scoring Report — {context.get('date','')}\n")

    lines.append("## Run Metadata")
    for k, v in context.get("meta", {}).items():
        lines.append(f"- {k}: {v}")
        
    lines.append("\n---\n")

    ranked = context.get("ranked", [])
    lines.append(f"## Top {len(ranked)} Ranked Ideas\n")

    for r in ranked:
        lines.append(f"### {r.get('rank','-')} {r.get('title','(no title)')} — **{r.get('total_score',0)}**")
        lines.append(f" - idea_id: {r.get('idea_id','-')}")
        lines.append(f" - tags: {', '.join(r.get('tags', [])) or '-'}")
        lines.append("- component_scores:")
        lines.append(f" - market: {r.get('market', 'unknown')}")
        lines.append(f" - feasibility: {r.get('feasibility', 'unknown')}")
        lines.append(f" - risk: {r.get('risk', 'unknown')}")
        lines.append(
                 f" - evidence: {r.get('signal_count', 0)} signals "
                 f"(avg reliability: {r.get('avg_reliability', 'n/a')})"
            )
        lines.append(f" - why: {r.get('explain', '')}\n")

    lines.append("---\n")
    lines.append("## Next Actions")
    lines.append("- Validate top ideas with 3 stakeholder interviews each")
    lines.append("- Build PoC for #1 within 1 week (define success metrics)")
    lines.append("- Expand signals coverage (news/papers/competitors)\n")

    out_path = report_dir / "summary.md"
    up = context.get("movers_up", []) or []
    down = context.get("movers_down", []) or []

    lines.append("\n## 🚀 Movers (Up)\n")
    if not up:
        lines.append("- (none)\n")
    else:
        for r in up:
           lines.append(f"- **{r.get('idea_id')}**  Δrank {r.get('rank_delta')}  Δscore {r.get('score_delta')}\n")

    lines.append("\n## 🔻 Movers (Down)\n")
    if not down:
        lines.append("- (none)\n")
    else:
        for r in down:
            lines.append(f"- **{r.get('idea_id')}**  Δrank {r.get('rank_delta')}  Δscore {r.get('score_delta')}\n")
    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"📝 summary.md saved → {out_path}")