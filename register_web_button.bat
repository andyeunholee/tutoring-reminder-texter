@echo off
setlocal
cd /d "%~dp0"
REM Registers the tutoring-texter:// link on THIS computer so a button on any
REM web page can start the app. Run it once per computer (again after moving
REM the folder). Writes only to HKCU, so no admin rights are needed.
REM
REM The command deliberately passes NO argument to run_app.bat: the browser
REM would hand over "tutoring-texter://open", and run_app.bat treats its first
REM argument as the URL to open in the browser - an endless loop.

if not "%~1"=="/quiet" (
  echo ==========================================================
  echo   Tutoring Reminder Texter - web button setup
  echo ==========================================================
  echo.
)

reg add "HKCU\Software\Classes\tutoring-texter" /ve /t REG_SZ /d "URL:Tutoring Reminder Texter" /f >nul
reg add "HKCU\Software\Classes\tutoring-texter" /v "URL Protocol" /t REG_SZ /d "" /f >nul
reg add "HKCU\Software\Classes\tutoring-texter\DefaultIcon" /ve /t REG_SZ /d "\"%~dp0app.ico\"" /f >nul
reg add "HKCU\Software\Classes\tutoring-texter\shell\open\command" /ve /t REG_SZ /d "\"%SystemRoot%\System32\cmd.exe\" /c \"\"%~dp0run_app.bat\"\"" /f >nul
if errorlevel 1 (
  echo [X] Could not write to the registry.
  if not "%~1"=="/quiet" pause
  exit /b 1
)

echo Web button link registered: tutoring-texter://open
if "%~1"=="/quiet" exit /b 0
echo.
echo Point a button on your website at:   tutoring-texter://open
echo The first click in each browser shows an "open app?" prompt -
echo tick "always allow" and it becomes one click from then on.
echo.
pause
