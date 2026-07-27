@echo off
REM Waits until the Streamlit server answers, then opens it in the default
REM browser. Kept in its own file because nesting this inside run_app.bat
REM needs quotes inside quotes, which cmd mangles.
REM %1 = URL to open (optional; defaults to the plain app URL).
setlocal
set "URL=%~1"
if "%URL%"=="" set "URL=http://localhost:8501"
for /l %%i in (1,1,90) do (
  curl -s -o nul --max-time 2 "http://localhost:8501/healthz"
  if not errorlevel 1 (
    start "" "%URL%"
    exit /b 0
  )
  timeout /t 2 /nobreak >nul
)
exit /b 1
