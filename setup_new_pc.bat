@echo off
setlocal
cd /d "%~dp0"
echo ==========================================================
echo   Tutoring Reminder Texter - new PC setup
echo ==========================================================
echo.

REM ---- 1. find a usable Python -------------------------------------------
set "PY="
py -3.14 -c "import sys" >nul 2>&1 && set "PY=py -3.14"
if not defined PY py -3.12 -c "import sys" >nul 2>&1 && set "PY=py -3.12"
if not defined PY py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY (
  echo [X] Python not found.
  echo     Install Python 3.12 or 3.14 from https://www.python.org/downloads/
  echo     and tick "Add python.exe to PATH" during setup.
  goto :end
)
echo [1/5] Python found: %PY%
%PY% --version

REM ---- 2. virtual environment ---------------------------------------------
REM Deliberately on local disk, never inside this Google Drive folder: reading
REM 13,000+ package files through Drive makes every launch ~7x slower.
set "VENV=%LOCALAPPDATA%\TutoringReminder\venv"
if exist "%VENV%\Scripts\python.exe" (
  echo [2/5] Environment already exists - reusing it
) else (
  echo [2/5] Creating the environment on your local disk ...
  echo       %VENV%
  %PY% -m venv "%VENV%"
  if errorlevel 1 (
    echo [X] Could not create the virtual environment.
    goto :end
  )
)

REM ---- 3. dependencies ----------------------------------------------------
echo [3/5] Installing Python packages ^(this can take a few minutes^) ...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip -q
"%VENV%\Scripts\pip.exe" install -r requirements.txt -q
if errorlevel 1 (
  echo [X] Package install failed. If it mentions "greenlet", install Python 3.12
  echo     and run this script again.
  goto :end
)

echo [4/5] Installing the browser engine ...
"%VENV%\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (
  echo [!] Browser engine install failed - sending may not work.
)

REM ---- 4. .env ------------------------------------------------------------
if exist ".env" (
  echo [5/5] .env already exists
) else (
  if exist ".env.example" (
    copy /y ".env.example" ".env" >nul
    echo [5/5] Created .env from .env.example
  )
)

echo.
echo ==========================================================
echo   Remaining steps you must do by hand
echo ==========================================================
if not exist "credentials.json" (
  echo.
  echo  [ ] credentials.json is MISSING.
  echo      Copy it from your other PC ^(same folder as this script^).
  echo      Carry it on a USB stick - do not email or chat it.
)
findstr /C:"ROSTER_SPREADSHEET_ID=" ".env" 2>nul | findstr /R "ROSTER_SPREADSHEET_ID=." >nul
if errorlevel 1 (
  echo.
  echo  [ ] .env has no ROSTER_SPREADSHEET_ID yet.
  echo      Open .env and paste the roster sheet ID from your other PC,
  echo      or run create_roster_sheet.bat to make a new sheet.
)
where chrome >nul 2>&1
if errorlevel 1 if not exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
  echo.
  echo  [ ] Google Chrome not detected.
  echo      Install it from https://www.google.com/chrome/
  echo      ^(Google blocks sign-in from the bundled test browser.^)
)
echo.
echo  [ ] Run login_google_voice.bat and sign in to Google Voice.
echo  [ ] Then run run_app.bat. The first search opens a Google consent
echo      window - approve it once.
echo.
echo Setup finished.

:end
echo.
pause
