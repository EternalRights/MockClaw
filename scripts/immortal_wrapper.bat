@echo off
REM MockClaw Immortal Wrapper - Life Support System
REM Auto-restarts agent on crash forever

title MockClaw Immortal Agent - Life Support

set COUNTER=0
set MAX_ITERATIONS=1000

:loop
set /a COUNTER+=1
echo.
echo ============================================================
echo [WRAPPER] MockClaw Immortal Agent - Iteration #%COUNTER%
echo [WRAPPER] Time: %time% - %date%
echo ============================================================
echo.

cd /d D:\mockclaw-immortal
python -u src/main.py --agent-mode 2>&1
set EXIT_CODE=%errorlevel%

echo.
echo [WRAPPER] Agent exited with code %EXIT_CODE%

if %EXIT_CODE% EQU 0 (
    echo [WRAPPER] Clean exit. Respawning in 5 seconds...
) else (
    echo [WRAPPER] CRASH DETECTED! Analyzing failure...
    echo [%date% %time%] Crash code: %EXIT_CODE%, iteration: %COUNTER% >> logs\crash_history.log
)

echo [WRAPPER] Cleaning up resources...
docker ps -aq 2>nul | findstr /r "^" && (for /f %%i in ('docker ps -aq') do docker stop %%i 2>nul & docker rm %%i 2>nul)
del /q generated_mocks\* 2>nul
for /d /r src %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul

echo [WRAPPER] Respawning in 5 seconds...
timeout 5 /nobreak >nul

if %COUNTER% LSS %MAX_ITERATIONS% goto loop

echo [WRAPPER] Max iterations reached. Terminating.
pause
