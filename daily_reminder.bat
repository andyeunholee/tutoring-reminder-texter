@echo off
REM Run by the 4pm scheduled task. Opens the app already showing TOMORROW's
REM [TUT] sessions, so the messages are on screen ready to review and send.
REM Nothing is sent automatically - sending stays a deliberate click.
cd /d "%~dp0"
call "%~dp0run_app.bat" "http://localhost:8501/?auto=1"
