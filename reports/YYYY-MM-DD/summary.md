# Idea Scoring Report — {{date}}

## Run Metadata
- run_id: {{run_id}}
- model: {{model_version}}
- total_ideas: {{total_ideas}}
- total_signals: {{total_signals}}
- generated_at: {{generated_at}}

---

## Top {{top_n}} Ranked Ideas
{{#each ranked}}
### {{rank}}) {{title}} — **{{total_score}}**
- idea_id: {{idea_id}}
- tags: {{tags}}
- component_scores:
  - market: {{market}}
  - feasibility: {{feasibility}}
  - risk: {{risk}}
  - evidence: {{evidence}}
- evidence: {{signal_count}} signals (avg reliability: {{avg_reliability}})
- why: {{explain}}

{{/each}}

---

## Risk Watchlist (High Risk)
{{#each high_risk}}
- {{title}} (idea_id: {{idea_id}}) — risk={{risk}} / 이유: {{risk_reason}}
{{/each}}

---

## Next Actions
- Validate top ideas with 3 stakeholder interviews each
- Build PoC for #1 within 1 week (define success metrics)
- Expand signals coverage (news/papers/competitors) to stabilize evidence score