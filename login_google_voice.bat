@echo off
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\TutoringReminder\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"
"%PY%" sms\setup_gv_login.py
pause
