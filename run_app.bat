@echo off
title Tutoring Reminder Texter - keep this window open
cd /d "%~dp0"

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

REM Already running? Starting a second server would bind another port while
REM the browser keeps landing on the first one - confusing, and the older
REM instance serves stale code after an update.
curl -s -o nul --max-time 2 http://localhost:8501/healthz
if not errorlevel 1 (
  echo The app is ALREADY running - opening the existing one in your browser.
  echo.
  echo If it misbehaves after an update, close every one of these black
  echo windows and start again from the desktop icon.
  start "" "http://localhost:8501"
  timeout /t 5 /nobreak >nul
  exit /b 0
)

REM Open the browser once the server is actually listening, so the user never
REM lands on an error page. Streamlit's own auto-open does not fire when the
REM window is started minimised from a desktop shortcut.
start "" /b "%~dp0_open_browser.bat"

".venv\Scripts\python.exe" -m streamlit run app.py --server.headless true

echo.
echo The app has stopped.
pause
