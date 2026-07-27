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

REM Registered through PowerShell rather than schtasks so three things can be
REM set that schtasks /create cannot express, and that this task needs:
REM   MultipleInstances=Parallel  - the app window from yesterday must not
REM                                 block today's trigger
REM   LogonType=Interactive       - the window has to appear on your desktop
REM   ExecutionTimeLimit=none     - the app may stay open all evening
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$act = New-ScheduledTaskAction -Execute '%~dp0daily_reminder.bat' -WorkingDirectory '%~dp0';" ^
  "$trg = New-ScheduledTaskTrigger -Daily -At '%RUNTIME%';" ^
  "$prn = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited;" ^
  "$set = New-ScheduledTaskSettingsSet -MultipleInstances Parallel -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable;" ^
  "Register-ScheduledTask -TaskName '%TASKNAME%' -Action $act -Trigger $trg -Principal $prn -Settings $set -Force | Out-Null;" ^
  "Write-Host 'Registered.'"

if errorlevel 1 (
  echo.
  echo [X] Could not register the task.
  goto :end
)

echo.
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
