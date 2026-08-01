@echo off
title Tutoring Reminder Texter - keep this window open
cd /d "%~dp0"

REM Prefer the venv on local disk. Reading 13,000+ package files through the
REM Google Drive filesystem makes startup roughly seven times slower.
set "PY=%LOCALAPPDATA%\TutoringReminder\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"

echo ==========================================================
echo   Tutoring Reminder Texter
echo ==========================================================
echo.
echo   The app opens in your web browser in a moment.
echo   KEEP THIS BLACK WINDOW OPEN while you use the app.
echo   Closing this window shuts the app down.
echo.
echo   If the browser does not open, go to:  http://localhost:8501
echo ==========================================================
echo.

REM %1 = URL to open (the 2pm task passes one that auto-searches tomorrow).
set "APP_URL=%~1"
if "%APP_URL%"=="" set "APP_URL=http://localhost:8501"

REM Already running? Starting a second server would bind another port while
REM the browser keeps landing on the first one - confusing, and the older
REM instance serves stale code after an update.
curl -s -o nul --max-time 2 http://localhost:8501/healthz
if not errorlevel 1 (
  echo The app is ALREADY running - opening the existing one in your browser.
  echo.
  echo If it misbehaves after an update, close every one of these black
  echo windows and start again from the desktop icon.
  start "" "%APP_URL%"
  timeout /t 5 /nobreak >nul
  exit /b 0
)

REM Open the browser once the server is actually listening, so the user never
REM lands on an error page. Streamlit's own auto-open does not fire when the
REM window is started minimised from a desktop shortcut.
start "" /b cmd /c ""%~dp0_open_browser.bat" "%APP_URL%""

"%PY%" -m streamlit run app.py --server.headless true

echo.
echo The app has stopped.
pause
