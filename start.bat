@echo off
echo ============================================================
echo                    MockClaw Startup
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/1] Starting Backend (Brain API)...
start "MockClaw Backend" cmd /k "python src\brain.py"
timeout /t 2 /nobreak >nul

echo.
echo ============================================================
echo  Service Started!
echo  Backend:  http://localhost:8000
echo  API Docs: http://localhost:8000/docs
echo ============================================================
echo.
echo Press any key to open the API docs...
pause >nul
start http://localhost:8000/docs
