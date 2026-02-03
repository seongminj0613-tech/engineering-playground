@echo off
setlocal

REM ✅ Always run from this .bat location (project root)
cd /d "%~dp0"

echo ==========================================
echo [1/4] Pipeline (ingest -> scoring -> reports)
echo ==========================================
python app\main.py
IF ERRORLEVEL 1 (
  echo ❌ app\main.py failed
  exit /b 1
)

echo ==========================================
echo [2/4] Generate meeting ranking markdown
echo ==========================================
python app\presentation\generate_meeting_rank.py
IF ERRORLEVEL 1 (
  echo ❌ generate_meeting_rank.py failed
  exit /b 1
)

echo ==========================================
echo [3/4] Plot meeting ranking chart
echo ==========================================
python app\presentation\plot_meeting_rank.py
IF ERRORLEVEL 1 (
  echo ❌ plot_meeting_rank.py failed
  exit /b 1
)

echo ==========================================
echo [4/4] Generate idea ranking (Top ideas inside meeting)
echo ==========================================
python app\presentation\generate_idea_rank.py
python app\presentation\plot_idea_rank.py

echo ✅ DONE. Outputs:
echo - reports\latest_meeting_rank.md
echo - reports\charts\meeting_rank.png
echo - reports\latest_idea_rank.md
echo - reports\charts\idea_rank.png
endlocal