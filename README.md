# 🚀 Meeting Decision Engine (Main Project)

AI 기반 회의 아이디어 평가 & 의사결정 지원 시스템
Github Pages에서는 정적 데모로 동작합니다
실제 분석 기능은 로컬에서 FastAPI 서버 실행시 동작합니다

👉 **Live Demo:**  
[Meeting Decision Engine 바로가기]
(https://seongminj0613-tech.github.io/engineering-playground/meeting_app/index.html)

---

## SignalRank — AI 기반 아이디어 우선순위 분석 시스템
실시간 데이터와 아이디어를 기반으로 실행 가능성과 시장성을 점수화하여 아이디어를 자동으로 랭킹화하고 변화 추이를 추적하는 운영형 데이터 파이프라인

운영형 자동데이터 파이프라인
아이디어  →  점수화  →  랭킹  →  히스토리  → 배포
자동으로 실행되는 DevOps 기반 분석 시스템


👉 **Live Dashboard:**  
[SignalRank Dashboard]
(https://seongminj0613-tech.github.io/engineering-playground/)
- Workflow (GitHub Actions): `Actions` 탭에서 daily run 로그 확인 가능
- History snapshots: `/docs/history/` 에 날짜별 기록 페이지 자동 생성
- History data: `/docs/history/data/` 에 날짜별 JSON 스냅샷 저장

---

## 📌 프로젝트 개요

브레인스토밍과 회의에서는 많은 아이디어가 나오지만  
객관적인 기준 없이 사라지는 경우가 많습니다.
SignalRank는  
뉴스·기술 트렌드·아이디어 데이터를 수집하여 
정량적 기준으로 점수화하여  
실행 가능성 있는 아이디어를 자동으로 선별하고  
변화 흐름까지 추적하는 시스템을 목표로 개발.

단순 시각화 프로젝트가 아니라  
실제 운영 가능한 자동화 데이터 파이프라인 구축을 중심으로 설계하였습니다.

---

## 🏗️ System Architecture

Ingestion Layer  
→ Signal & Evidence Extraction  
→ Scoring Engine (score_breakdown 기반)  
→ Validation Layer  
→ Ranking & Snapshot 생성  
→ GitHub Actions Automation  
→ GitHub Pages 배포

GitHub Actions를 통해  
데이터 수집부터 결과 배포까지  
자동으로 실행되는 구조로 구성됨

각 단계는 독립 모듈로 구성되었으며 scoring 로직 변경이나 데이터 소스 확장 시 파이프라인 전체를 수정하지 않고 확장 가능하도록 설계하였습니다.

---

## ⚙️ Core Features

### 1. Daily Idea Scoring Pipeline
- 뉴스/아이디어 데이터 수집
- 실행 가능성/시장성 기반 점수 계산
- 자동 랭킹 생성

### 2. Ranking History Tracking
- 날짜별 랭킹 스냅샷 저장
- 순위 변화 추적
- 히스토리 페이지 자동 생성

### 3. Diff Visualization
- 전일 대비 랭킹 상승/하락 분석
- 아이디어 트렌드 흐름 파악

### 4. Automated Pipeline
- GitHub Actions daily run
- 데이터 → 점수화 → 랭킹 → 페이지 배포 자동화
- 완전 무인 운영 구조

### Scoring Model Design
- score_breakdown 기반 설명 가능한 점수 구조
- total_score = sum(score_breakdown) 검증 구조
- evidence + signals 기반 scoring
- deterministic scoring pipeline (재현성 보장)
점수 계산 과정을 블랙박스가 아니라 검증 가능한 deterministic 구조로 설계
운영 환경에서도 재현성과 신뢰성을 유지하도록 설계
---

## 🧠 Tech Stack

- Python (Data pipeline)
- GitHub Actions (CI/CD 자동 실행)
- JSON 기반 데이터 구조 설계
- Static Web Dashboard (GitHub Pages)
- Git version history tracking

---
## ▶️ How to Run (Local)

```bash
# 1) install
pip install -r requirements.txt

# 2) run pipeline
python app/pipeline.py

# 3) render dashboard
python app/presentation/render_topn_html.py
```

---


## 📊 Live Result

Daily ranking dashboard  
Ranking history tracking  
자동 실행 파이프라인 운영 중

👉 https://seongminj0613-tech.github.io/engineering-playground/

---

## 🎯 What I Focused On

이 프로젝트는  
단순한 시각화나 크롤링 프로젝트가 아니라

데이터 수집 → 점수화 → 랭킹 → 기록 → 자동배포까지 이어지는  
**운영형 데이터 파이프라인 설계**를 목표로 제작

DevOps/Cloud 환경에서  
자동 실행되는 분석 시스템 구축을 중점으로 발전시키고 있습니다.

특히 점수 산정 과정을 블랙박스가 아니라 설명 가능한 구조(score_breakdown)
로 설계한 것이 핵심입니다.
---

## 🚀 Next Step (Planned)

- Scoring 품질 고도화 (trend weight / rank delta)
- Evidence 기반 신뢰도 점수 모델
- Docker + AWS 운영 환경 확장
- AI는 scoring 결정이 아닌 signal/evidence 보조로 활용 예정

## 👨‍💻 My Role

개인 프로젝트로  
데이터 파이프라인 설계부터  
랭킹 알고리즘 구성  
자동 실행 환경 구축  
대시보드 배포까지 전 과정 직접 구현

단순 기능 구현이 아니라  
"운영되는 시스템" 구축을 목표로 개발

## 💡 Why This Project Matters

단순한 CRUD나 시각화 프로젝트가 아니라  
"자동으로 실행되는 데이터 기반 의사결정 시스템"을  
직접 설계하고 구현해보고 싶었습니다.

데이터 수집 → 분석 → 랭킹 → 기록 → 자동 배포까지  
전체 흐름을 하나의 시스템으로 구성하면서  

DevOps/Cloud 환경에서  
운영되는 서비스 구조를 이해하는 것을 목표로 했습니다.

## 🐳 Run with Docker
Docker 환경에서도 전체 데이터 파이프라인이
정상 동작하도록 구성되었습니다.

- docker build → 실행 성공
- 파이프라인 실행 및 결과 생성 확인
- GitHub Pages 대시보드 반영 구조

개발 환경이 아닌
컨테이너 기반 동일 환경에서
재현 가능한 시스템으로 설계했습니다.