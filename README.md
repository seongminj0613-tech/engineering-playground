# Idea Scoring & Ranking System

## What
애자일 / 스크럼 / 브레인스토밍 회의에서 나온 아이디어를  
외부 신호(뉴스, 트렌드, 근거 링크) 기반으로 점수화하여  
객관적인 랭킹과 히스토리 변화를 제공하는 자동화 시스템입니다.

## Why
회의 아이디어는 종종 분위기, 발언권, 직관에 의해 선택되거나 버려집니다.  
이 프로젝트는 아이디어를 **데이터 기반으로 비교**하여  
아이디어의 변별력과 의사결정 품질을 높이는 것을 목표로 합니다.

## Key Features
- 아이디어 자동 점수화 및 Top-N 랭킹
- 날짜별 히스토리 스냅샷 저장
- Rank Delta(순위 변화) 시각화
- GitHub Actions 기반 Daily 자동 실행
- GitHub Pages를 통한 결과 공유

# engineering-playground
시장 분석 자동화, 클라우드 인프라, 시스템 실험을 위한 엔지니어링 플레이그라운드

## Demo: Agile Meeting Idea Ranking (Latest)

### 1) Meeting Productivity Ranking
- Report: `reports/latest_meeting_rank.md`

![Meeting Rank](reports/charts/meeting_rank.png)

### 2) Top Ideas Inside Meeting
- Report: `reports/latest_idea_rank.md`

![Idea Rank](reports/charts/idea_rank.png)

> The files above are automatically updated by the daily GitHub Actions pipeline.  
> `latest_*` files always point to the most recent successful pipeline run.

## Automation (GitHub Actions)

This pipeline runs automatically every day at **09:00 KST (00:00 UTC)**  
and can also be triggered manually via GitHub Actions.

![Daily Idea Pipeline - Success](docs/actions_success.png)

- ⚙️ Execution: `python -m app.main`
- 📦 Outputs:
  - `reports/`
  - `snapshots/`
  - `data/reports/`

Workflow file: `.github/workflows/daily.yml`

---

## Run Locally

> Run the commands from the repository root (where `requirements.txt` exists).

```bash
pip install -r requirements.txt
python -m app.main