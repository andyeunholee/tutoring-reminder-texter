@echo off
REM Run by the daily scheduled task. Opens the app already showing TOMORROW's
REM [TUT] sessions, ready to review. Nothing is sent automatically.
REM
REM This file MUST finish within seconds. The task is registered with
REM MultipleInstancesPolicy=IgnoreNew, so if this script sat here for as long
REM as the app was open, tomorrow's trigger would be silently skipped.
cd /d "%~dp0"
set "URL=http://localhost:8501/?auto=1"

REM Already running (left open from yesterday)? Just bring it up.
curl -s -o nul --max-time 3 http://localhost:8501/healthz
if not errorlevel 1 (
  start "" "%URL%"
  exit /b 0
)

REM Otherwise start the app in its own window and return immediately.
start "" "%~dp0run_app.bat" "%URL%"
exit /b 0
