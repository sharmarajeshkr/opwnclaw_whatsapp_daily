@echo off
setlocal enabledelayedexpansion

:: ────────────────────────────────────────────────────────────────────────────
:: CONFIGURATION
:: ────────────────────────────────────────────────────────────────────────────
set APP_NAME=OpenClaw All-in-One Launcher
set VENV_PATH=.\venv
set PYTHON_EXE=%VENV_PATH%\Scripts\python.exe
set STREAMLIT_EXE=%VENV_PATH%\Scripts\streamlit.exe

title %APP_NAME%
cls

:: ── Professional Header ─────────────────────────────────────────────────────
powershell -Command "Write-Host '--------------------------------------------------' -ForegroundColor Cyan"
powershell -Command "Write-Host '      OpenClaw - Multi-User Bot Launcher         ' -ForegroundColor White -BackgroundColor Blue"
powershell -Command "Write-Host '--------------------------------------------------' -ForegroundColor Cyan"
echo.

:: ── Check Environment ───────────────────────────────────────────────────────
if not exist ".env" (
    powershell -Command "Write-Host '[WRN] .env file not found!' -ForegroundColor Yellow"
    if exist ".env.example" (
        echo Copying .env.example to .env ...
        copy .env.example .env > nul
        powershell -Command "Write-Host '[OK] Created .env from example. Please update your API keys!' -ForegroundColor Green"
    ) else (
        powershell -Command "Write-Host '[ERR] .env.example also missing. Please create .env manually.' -ForegroundColor Red"
        pause
        exit /b 1
    )
)

:: ── Check Virtual Environment ───────────────────────────────────────────────
if not exist "%VENV_PATH%" (
    powershell -Command "Write-Host '[INF] Virtual environment not found. Initializing with Python 3.12...' -ForegroundColor Cyan"
    py -3.12 -m venv venv
    if !ERRORLEVEL! neq 0 (
        powershell -Command "Write-Host '[ERR] Failed to create virtual environment using Python 3.12.' -ForegroundColor Red"
        pause
        exit /b 1
    )
    
    powershell -Command "Write-Host '[INF] Installing requirements... (This may take a minute)' -ForegroundColor Cyan"
    %VENV_PATH%\Scripts\pip install -r requirements.txt
    if !ERRORLEVEL! neq 0 (
        powershell -Command "Write-Host '[ERR] Failed to install requirements.' -ForegroundColor Red"
        pause
        exit /b 1
    )
    powershell -Command "Write-Host '[OK] Environment setup complete.' -ForegroundColor Green"
)

:: ── Cleanup Existing Processes (Optional Safety) ──────────────────────────
powershell -Command "Write-Host '[INF] Cleaning up stale bot processes...' -ForegroundColor Gray"
powershell -Command "$p = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'main.py' }; if($p) { $p | Stop-Process -Force; Write-Host '[OK] Terminated existing daemon sessions.' -ForegroundColor Green } else { Write-Host '[OK] No active daemon sessions found.' -ForegroundColor Gray }"

:: ── Launching ───────────────────────────────────────────────────────────────
echo.
powershell -Command "Write-Host '[1/2] Launching Bot Daemon (main.py)...' -ForegroundColor Cyan"
start "OpenClaw Daemon" /min "%PYTHON_EXE%" main.py

powershell -Command "Write-Host '[2/2] Launching Dashboard UI (app.py)...' -ForegroundColor Cyan"
echo.
"%STREAMLIT_EXE%" run app.py

if %ERRORLEVEL% neq 0 (
    echo.
    powershell -Command "Write-Host '[ERR] Dashboard crashed or exited with error.' -ForegroundColor Red"
    pause
)

endlocal
