@echo off
setlocal enabledelayedexpansion

echo.
echo 🚀 MockClaw Quick Install
echo ========================
echo.

set PYTHON_CMD=

where python >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
) else (
    where python3 >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=python3
    )
)

if "%PYTHON_CMD%"=="" (
    echo ❌ Error: Python not found
    echo Please install Python 3.11 or higher and try again
    exit /b 1
)

for /f "tokens=2" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✅ Found Python: %PYTHON_VERSION%

for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set MAJOR=%%a
    set MINOR=%%b
)

if %MAJOR% lss 3 (
    goto :version_error
) else if %MAJOR% equ 3 (
    if %MINOR% lss 11 (
        goto :version_error
    )
)
goto :version_ok

:version_error
echo ❌ Error: MockClaw requires Python 3.11 or higher
echo Current version: %PYTHON_VERSION%
exit /b 1

:version_ok
echo.
echo 📦 Setting up virtual environment...

if exist venv (
    echo ⚠️  Virtual environment already exists
    set /p RECREATE="Remove and recreate? (y/N) "
    if /i "!RECREATE!"=="y" (
        rmdir /s /q venv
    ) else (
        echo Using existing virtual environment
    )
)

if not exist venv (
    %PYTHON_CMD% -m venv venv
    echo ✅ Virtual environment created
)

echo.
echo 📥 Installing dependencies...

call venv\Scripts\activate.bat

pip install --upgrade pip -q
pip install -r src\requirements.txt -q

echo ✅ Dependencies installed

echo.
echo 🔧 Installing MockClaw...

pip install -e . -q

echo ✅ MockClaw installed

echo.
echo ✨ Installation complete!
echo.
echo Quick Start:
echo   1. Activate environment:  venv\Scripts\activate.bat
echo   2. Try quick example:     mockclaw example
echo   3. View documentation:    mockclaw --help
echo.
echo Or run directly:
echo   venv\Scripts\mockclaw.exe example
echo.
