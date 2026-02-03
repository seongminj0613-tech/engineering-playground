# engineering-playground
시장 분석 자동화, 클라우드 인프라, 시스템 실험을 위한 엔지니어링 플레이그라운드
## Demo: Agile Meeting Idea Ranking (Latest)

### 1) Meeting Productivity Ranking
- Report: `reports/latest_meeting_rank.md`
- Chart:

![Meeting Rank](reports/charts/meeting_rank.png)

### 2) Top Ideas Inside Meeting
- Report: `reports/latest_idea_rank.md`
- Chart:

![Idea Rank](reports/charts/idea_rank.png)

## Automated Daily Pipeline (CI)

This project runs a fully automated daily analysis pipeline using **GitHub Actions**.

- ⏰ **Schedule**: Daily at 09:00 KST (00:00 UTC)
- ⚙️ **Execution**: `python -m app.main`
- 🧠 **Pipeline**
  - Ingests meeting / idea data
  - Ranks meeting productivity and top ideas
  - Generates reports and visual graphs automatically
- 📦 **Outputs**
  - `reports/`
  - `snapshots/`
  - `data/reports/`

✅ Verified via GitHub Actions (CI)
🔗 Workflow: `.github/workflows/daily.yml`