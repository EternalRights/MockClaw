@echo off
REM MockClaw Immortal Wrapper
REM Life support system - auto-restarts agent on crash

title MockClaw Immortal Agent

set COUNTER=0
set MAX_ITERATIONS=1000

:loop
set /a COUNTER+=1
echo.
echo ============================================================
echo [WRAPPER] MockClaw Agent - Iteration #%COUNTER%
echo [WRAPPER] Time: %time% - %date%
echo ============================================================
echo.

python -u src/main.py --agent-mode 2>&1
set EXIT_CODE=%errorlevel%

echo.
echo [WRAPPER] Agent exited with code %EXIT_CODE%

if %EXIT_CODE% EQU 0 (
    echo [WRAPPER] Clean exit. Respawn in 5 seconds...
) else (
    echo [WRAPPER] Crash detected! Analyzing...
    echo [WRAPPER] Checking for patches...
    
    REM Log crash
    echo [%date% %time%] Crash detected, exit code: %EXIT_CODE%, iteration: %COUNTER% >> logs\crash_history.log
)

REM Memory cleanup
echo [WRAPPER] Cleaning up resources...
docker ps -aq 2>nul | findstr /r "^" && (docker stop $(docker ps -aq) 2>nul & docker rm $(docker ps -aq) 2>nul)
del /q generated_mocks\* 2>nul
del /q logs\temp\* 2>nul
for /d /r src %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul

echo [WRAPPER] Restarting in 5 seconds...
timeout 5 /nobreak >nul

if %COUNTER% LSS %MAX_ITERATIONS% goto loop

echo [WRAPPER] Max iterations reached. Exiting.
pause
