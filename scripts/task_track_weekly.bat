@echo off
chcp 65001 >nul
set PATH=C:\Users\shen.gang\.local\bin;C:\Users\shen.gang\AppData\Local\Programs\Python\Python311;%PATH%
cd /d D:\Claw\SNS
powershell.exe -ExecutionPolicy Bypass -File "D:\Claw\SNS\task_track_weekly.ps1" 2>&1 >> D:\Claw\SNS\task_log.txt
if %ERRORLEVEL% neq 0 (
    echo [%date% %time%] 任务执行失败 >> D:\Claw\SNS\task_log.txt
)
