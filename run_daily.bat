@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%cd%"

REM ✅ Always run from this .bat location (project root)
cd /d "%~dp0"

set LOG="%~dp0logs\daily_run.log"
if not exist "%~dp0logs" mkdir "%~dp0logs"
echo ===== %date% %time% START =====>> %LOG%

echo ==========================================>> %LOG%
echo [1/5] Pipeline (ingest -> scoring -> reports)>> %LOG%
echo ==========================================>> %LOG%
python -m app.main >> %LOG% 2>&1
IF ERRORLEVEL 1 (
  echo ❌ app\main.py failed >> %LOG%
  exit /b 1
)

echo ==========================================>> %LOG%
echo [2/5] Generate meeting ranking markdown>> %LOG%
echo ==========================================>> %LOG%
python app\presentation\generate_meeting_rank.py >> %LOG% 2>&1
IF ERRORLEVEL 1 (
  echo ❌ generate_meeting_rank.py failed >> %LOG%
  exit /b 1
)

echo ==========================================>> %LOG%
echo [3/5] Plot meeting ranking chart>> %LOG%
echo ==========================================>> %LOG%
python app\presentation\plot_meeting_rank.py >> %LOG% 2>&1
IF ERRORLEVEL 1 (
  echo ❌ plot_meeting_rank.py failed >> %LOG%
  exit /b 1
)

echo ==========================================>> %LOG%
echo [4/5] Generate idea ranking + plot>> %LOG%
echo ==========================================>> %LOG%
python app\presentation\generate_idea_rank.py >> %LOG% 2>&1
IF ERRORLEVEL 1 (
  echo ❌ generate_idea_rank.py failed >> %LOG%
  exit /b 1
)

python app\presentation\plot_idea_rank.py >> %LOG% 2>&1
IF ERRORLEVEL 1 (
  echo ❌ plot_idea_rank.py failed >> %LOG%
  exit /b 1
)

echo ==========================================>> %LOG%
echo [5/5] Weekly diff>> %LOG%
echo ==========================================>> %LOG%
python app\presentation\weekly_diff.py >> %LOG% 2>&1
IF ERRORLEVEL 1 (
  echo ❌ weekly_diff.py failed >> %LOG%
  exit /b 1
)

git add docs >> %LOG% 2>&1
git diff --cached --quiet
IF %ERRORLEVEL%==0 (
  echo No changes to commit >> %LOG%
) ELSE (
  git commit -m "chore(daily): update docs" >> %LOG% 2>&1
  git push >> %LOG% 2>&1
)

echo ✅ DONE >> %LOG%
echo ===== %date% %time% END =====>> %LOG%
endlocal