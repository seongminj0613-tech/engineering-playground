# Graph Insights (2026-02-03)

## 1) Top Hub Nodes (by Degree)
- 1. **Generator(Prompt-only)** — degree=38, type=pattern
- 2. **Agent** — degree=8, type=pattern
- 3. **hallucination** — degree=7, type=risk
- 4. **meeting_memory** — degree=7, type=feature
- 5. **action_items** — degree=6, type=feature

## 2) Risk Nodes & Direct Neighbors
- **hallucination** → Generator(Prompt-only), case_13986828, case_34613598, case_8958059, case_45929247, case_327937, case_31768298
- **privacy** → Generator(Prompt-only), case_24547098
- **latency** → Generator(Prompt-only), case_8958059

## 3) Feature → Connected Cases
- **action_items** → cases(5): case_13986828, case_24547098, case_34613598, case_35547859, case_45929247
- **meeting_memory** → cases(5): case_8958059, case_13986828, case_24547098, case_34613598, case_46705212
- **cost_explosion** → cases(4): case_17420399, case_24547098, case_46297830, case_46705212
- **structured_output** → cases(2): case_12983331, case_46705212
- **multilingual** → cases(2): case_27882350, case_46493969
- **speaker_labels** → cases(2): case_327937, case_46297830
- **pii_redaction** → cases(1): case_24547098
- **hallucination_guard** → cases(1): case_13986828

## 4) Risk Impact Zone (1-hop / 2-hop)
- **hallucination**
  - 1-hop(7): Generator(Prompt-only), case_13986828, case_8958059, case_34613598, case_327937, case_45929247, case_31768298
<<<<<<< HEAD
  - 2-hop(38): Generator(Prompt-only), meeting_memory, case_24547098, cost_explosion, action_items, case_13986828, speaker_labels, structured_output, multilingual, case_34613598, case_8958059, case_45929247, case_327937, case_35547859, privacy, case_46493969, latency, case_17420399, pii_redaction, hallucination_guard, case_31768298, case_12983331, case_46528245, case_45348151, case_34425801, case_43741559, case_44200037, case_33719870, case_44271745, case_44148559, case_34732840, case_38446289, case_39006262, case_35439454, case_13493311, case_34148357, case_46353596, case_35549526
- **privacy**
  - 1-hop(2): Generator(Prompt-only), case_24547098
  - 2-hop(38): Generator(Prompt-only), hallucination, meeting_memory, case_24547098, cost_explosion, action_items, case_13986828, speaker_labels, structured_output, multilingual, case_34613598, case_8958059, case_45929247, case_327937, case_35547859, case_46493969, latency, case_17420399, pii_redaction, hallucination_guard, case_31768298, case_12983331, case_46528245, case_45348151, case_34425801, case_43741559, case_44200037, case_33719870, case_44271745, case_44148559, case_34732840, case_38446289, case_39006262, case_35439454, case_13493311, case_34148357, case_46353596, case_35549526
- **latency**
  - 1-hop(2): Generator(Prompt-only), case_8958059
  - 2-hop(38): Generator(Prompt-only), hallucination, meeting_memory, case_24547098, cost_explosion, action_items, case_13986828, speaker_labels, structured_output, multilingual, case_34613598, case_8958059, case_45929247, case_327937, case_35547859, privacy, case_46493969, case_17420399, pii_redaction, hallucination_guard, case_31768298, case_12983331, case_46528245, case_45348151, case_34425801, case_43741559, case_44200037, case_33719870, case_44271745, case_44148559, case_34732840, case_38446289, case_39006262, case_35439454, case_13493311, case_34148357, case_46353596, case_35549526
=======
  - 2-hop(38): Generator(Prompt-only), meeting_memory, action_items, cost_explosion, case_24547098, case_13986828, case_8958059, structured_output, multilingual, speaker_labels, case_34613598, case_45929247, case_327937, privacy, case_12983331, hallucination_guard, case_46493969, case_31768298, latency, pii_redaction, case_17420399, case_35547859, case_45348151, case_44271745, case_44148559, case_34148357, case_34425801, case_43741559, case_35439454, case_33719870, case_39006262, case_46353596, case_44200037, case_46528245, case_38446289, case_35549526, case_13493311, case_34732840
- **privacy**
  - 1-hop(2): Generator(Prompt-only), case_24547098
  - 2-hop(38): Generator(Prompt-only), meeting_memory, hallucination, action_items, cost_explosion, case_24547098, case_13986828, case_8958059, structured_output, multilingual, speaker_labels, case_34613598, case_45929247, case_327937, case_12983331, hallucination_guard, case_46493969, case_31768298, latency, pii_redaction, case_17420399, case_35547859, case_45348151, case_44271745, case_44148559, case_34148357, case_34425801, case_43741559, case_35439454, case_33719870, case_39006262, case_46353596, case_44200037, case_46528245, case_38446289, case_35549526, case_13493311, case_34732840
- **latency**
  - 1-hop(2): Generator(Prompt-only), case_8958059
  - 2-hop(38): Generator(Prompt-only), meeting_memory, hallucination, action_items, cost_explosion, case_24547098, case_13986828, case_8958059, structured_output, multilingual, speaker_labels, case_34613598, case_45929247, case_327937, privacy, case_12983331, hallucination_guard, case_46493969, case_31768298, pii_redaction, case_17420399, case_35547859, case_45348151, case_44271745, case_44148559, case_34148357, case_34425801, case_43741559, case_35439454, case_33719870, case_39006262, case_46353596, case_44200037, case_46528245, case_38446289, case_35549526, case_13493311, case_34732840
>>>>>>> bc29a2e (chore: update workflow and README)

## 5) Impact Score Top Nodes
- 1. **Generator(Prompt-only)** — score=9, degree=38, type=pattern
- 2. **case_8958059** — score=7, degree=4, type=case
- 3. **case_13986828** — score=5, degree=5, type=case
- 4. **case_34613598** — score=5, degree=4, type=case
- 5. **case_327937** — score=5, degree=3, type=case
- 6. **case_45929247** — score=5, degree=3, type=case
- 7. **case_31768298** — score=5, degree=2, type=case
- 8. **case_24547098** — score=5, degree=6, type=case
- 9. **meeting_memory** — score=3, degree=7, type=feature
<<<<<<< HEAD
- 10. **cost_explosion** — score=3, degree=6, type=feature
=======
- 10. **action_items** — score=3, degree=6, type=feature
>>>>>>> bc29a2e (chore: update workflow and README)

## 6) Centrality (Betweenness / PageRank)
### 6.1 Betweenness Centrality (Top 10)
- 1. **Generator(Prompt-only)** — betweenness=0.1585, degree=38, type=pattern
- 2. **Agent** — betweenness=0.0052, degree=8, type=pattern
- 3. **hallucination** — betweenness=0.0000, degree=7, type=risk
- 4. **action_items** — betweenness=0.0000, degree=6, type=feature
- 5. **meeting_memory** — betweenness=0.0000, degree=7, type=feature
- 6. **cost_explosion** — betweenness=0.0000, degree=6, type=feature
- 7. **case_46705212** — betweenness=0.0000, degree=4, type=case
- 8. **structured_output** — betweenness=0.0000, degree=4, type=feature
- 9. **case_46528245** — betweenness=0.0000, degree=1, type=case
- 10. **case_46493969** — betweenness=0.0000, degree=2, type=case

### 6.2 PageRank (Top 10)
- 1. **Generator(Prompt-only)** — pagerank=0.2110, degree=38, type=pattern
- 2. **hallucination** — pagerank=0.0466, degree=7, type=risk
- 3. **cost_explosion** — pagerank=0.0443, degree=6, type=feature
- 4. **meeting_memory** — pagerank=0.0429, degree=7, type=feature
- 5. **action_items** — pagerank=0.0424, degree=6, type=feature
- 6. **multilingual** — pagerank=0.0418, degree=4, type=feature
- 7. **structured_output** — pagerank=0.0393, degree=4, type=feature
- 8. **speaker_labels** — pagerank=0.0385, degree=4, type=feature
- 9. **latency** — pagerank=0.0305, degree=2, type=risk
- 10. **hallucination_guard** — pagerank=0.0300, degree=2, type=feature
