@echo off
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\TutoringReminder\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"
echo Syncing the roster sheet with names found on the calendar...
echo (Creates the sheet the first time; afterwards only ADDS missing names.)
"%PY%" scripts\create_roster_sheet.py --seed-days 60 --future-days 120
pause
