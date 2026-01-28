@echo off
chcp 65001 > nul

cd /d "E:\boot camp data\프로젝트"

REM (선택) 가상환경 쓰면 아래 주석 해제하고 경로 맞추기
REM call ".venv\Scripts\activate"

python hn_fetch.py >> "reports\cron_log.txt" 2>>&1