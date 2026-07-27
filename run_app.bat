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

REM Open the browser once the server is actually listening, so the user never
REM lands on an error page. Streamlit's own auto-open does not fire when the
REM window is started minimised from a desktop shortcut.
start "" /b "%~dp0_open_browser.bat"

".venv\Scripts\python.exe" -m streamlit run app.py --server.headless true

echo.
echo The app has stopped.
pause
