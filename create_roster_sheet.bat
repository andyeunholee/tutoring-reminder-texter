@echo off
cd /d "%~dp0"
echo Syncing the roster sheet with names found on the calendar...
echo (Creates the sheet the first time; afterwards only ADDS missing names.)
".venv\Scripts\python.exe" scripts\create_roster_sheet.py --seed-days 60 --future-days 120
pause
