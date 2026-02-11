# SignalRank System Architecture

## Overview
SignalRank는  
아이디어 데이터를 수집하고  
Signals + Evidence 기반 scoring을 수행한 뒤  
Daily ranking과 history를 자동 생성하는  
운영형 데이터 파이프라인입니다.

---

## Pipeline Flow

Ingestion  
→ Signal & Evidence Extraction  
→ Scoring Engine  
→ Validation  
→ Ranking  
→ Snapshot 저장  
→ GitHub Pages 배포  

전체 과정은 GitHub Actions를 통해
daily 자동 실행됩니다.

---

## Core Components

### 1. Ingestion Layer
뉴스/아이디어 데이터 수집 및 정규화  
raw → structured row 변환

### 2. Signal & Evidence Extraction
아이디어 분석에 필요한 signals 생성  
점수 근거 evidence 생성

### 3. Scoring Engine
score_breakdown 기반 점수 계산  
total_score 산출

### 4. Validation Layer
total_score = sum(score_breakdown) 검증  
데이터 일관성 유지

### 5. Ranking System
Top-N 아이디어 랭킹 생성  
전일 대비 diff 계산

### 6. History Snapshot
날짜별 ranking JSON 저장  
history 페이지 자동 생성

### 7. Deployment
GitHub Actions → Pages 자동 배포  
완전 자동 운영 구조