@echo off
REM Waits until the Streamlit server answers, then opens it in the default
REM browser. Kept in its own file because nesting this inside run_app.bat
REM needs quotes inside quotes, which cmd mangles.
setlocal
set "URL=http://localhost:8501"
for /l %%i in (1,1,90) do (
  curl -s -o nul --max-time 2 "%URL%/healthz"
  if not errorlevel 1 (
    start "" "%URL%"
    exit /b 0
  )
  timeout /t 2 /nobreak >nul
)
exit /b 1
