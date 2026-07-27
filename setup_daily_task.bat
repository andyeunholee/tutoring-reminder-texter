@echo off
setlocal
cd /d "%~dp0"

set "TASKNAME=Tutoring Reminder Texter - Daily"
set "RUNTIME=%~1"
if "%RUNTIME%"=="" set "RUNTIME=16:00"

echo ==========================================================
echo   Daily reminder schedule
echo ==========================================================
echo.
echo   Task  : %TASKNAME%
echo   Time  : %RUNTIME% every day
echo   Action: open the app showing TOMORROW's [TUT] sessions
echo.
echo   Nothing is sent automatically. You still review the list
echo   and press the send button yourself.
echo.

schtasks /create /tn "%TASKNAME%" /tr "\"%~dp0daily_reminder.bat\"" /sc daily /st %RUNTIME% /f
if errorlevel 1 (
  echo.
  echo [X] Could not register the task.
  echo     Try running this file as Administrator ^(right-click, Run as administrator^).
  goto :end
)

echo.
echo Registered. Current setting:
schtasks /query /tn "%TASKNAME%" /fo list | findstr /i "TaskName Next Status"
echo.
echo To change the time:   setup_daily_task.bat 15:30
echo To run it now:        schtasks /run /tn "%TASKNAME%"
echo To remove it:         schtasks /delete /tn "%TASKNAME%" /f
echo.
echo NOTE: the task only fires while this computer is on and you are
echo       signed in. If the PC is asleep at %RUNTIME%, Windows runs it
echo       shortly after you wake it.

:end
echo.
pause
