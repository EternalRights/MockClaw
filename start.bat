@echo off
echo ============================================================
echo                    MockClaw Startup
echo ============================================================
echo.

cd /d D:\MockClaw

echo [1/2] Starting Backend (Brain API)...
start "MockClaw Backend" cmd /k "python src\brain.py"
timeout /t 2 /nobreak >nul

echo [2/2] Starting Frontend (Next.js)...
cd web
start "MockClaw Frontend" cmd /k "npm run dev"
timeout /t 3 /nobreak >nul

echo.
echo ============================================================
echo  Services Started!
echo  Backend:  http://localhost:8000
echo  Frontend: http://localhost:3000
echo ============================================================
echo.
echo Press any key to open the dashboard...
pause >nul
start http://localhost:3000
