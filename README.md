# SignalRank — AI 기반 아이디어 우선순위 분석 시스템

실시간 데이터와 아이디어를 기반으로  
실행 가능성과 시장성을 점수화하여  
아이디어를 자동으로 랭킹화하고 변화 추이를 추적하는  
운영형 데이터 파이프라인 프로젝트

👉 Live Dashboard  
https://seongminj0613-tech.github.io/engineering-playground/
- Workflow (GitHub Actions): `Actions` 탭에서 daily run 로그 확인 가능
- History snapshots: `/docs/history/` 에 날짜별 기록 페이지 자동 생성
- History data: `/docs/history/data/` 에 날짜별 JSON 스냅샷 저장

---

## 📌 프로젝트 개요

브레인스토밍과 회의에서는 많은 아이디어가 나오지만  
객관적인 기준 없이 사라지는 경우가 많다.

SignalRank는  
뉴스·기술 트렌드·아이디어 데이터를 수집하고  
정량적 기준으로 점수화하여  

**실행 가능성 있는 아이디어를 자동으로 선별하고  
변화 흐름까지 추적하는 시스템**을 목표로 한다.

단순 시각화 프로젝트가 아니라  
실제 운영 가능한 자동화 데이터 파이프라인 구축을 중심으로 설계하였습니다.

---

## 🏗️ System Architecture

Data Ingestion  
→ Idea scoring pipeline  
→ Ranking system  
→ Daily snapshot 저장  
→ Ranking 변화 추적  
→ GitHub Pages 자동 배포  

GitHub Actions를 통해  
데이터 수집부터 결과 배포까지  
완전 자동 실행 구조로 구성됨

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
**운영형 데이터 파이프라인 설계 경험**을 목표로 제작

DevOps/Cloud 환경에서  
자동 실행되는 분석 시스템 구축을 중점으로 발전시키고 있다.

---

## 🚀 Next Step (Planned)

- Docker 기반 실행 환경 구성
- AWS 배포 확장
- Vector DB 기반 신호 분석
- AI 기반 아이디어 평가 모델 고도화

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