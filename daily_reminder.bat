@echo off
REM Run by the daily scheduled task. Opens the app already showing TOMORROW's
REM [TUT] sessions, ready to review. Nothing is sent automatically.
cd /d "%~dp0"
set "URL=http://localhost:8501/?auto=1"

REM Left open from yesterday? Just bring that one to the screen and finish.
curl -s -o nul --max-time 3 http://localhost:8501/healthz
if not errorlevel 1 (
  start "" "%URL%"
  exit /b 0
)

REM Otherwise run the app here. This window stays for as long as the app runs;
REM the task is registered with MultipleInstances=Parallel so tomorrow's
REM trigger fires even while this one is still going.
call "%~dp0run_app.bat" "%URL%"
