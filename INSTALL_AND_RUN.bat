@echo off
setlocal enabledelayedexpansion

:: --- Configuration ---
set APP_NAME=OpenClaw All-in-One
set VENV_PATH=.\venv
set PYTHON_EXE=%VENV_PATH%\Scripts\python.exe
set STREAMLIT_EXE=%VENV_PATH%\Scripts\streamlit.exe

title %APP_NAME% - Installer & Launcher
cls

echo ==================================================
echo      OpenClaw - Multi-User Bot Installer         
echo ==================================================
echo.

:: 1. Check for .env
if not exist ".env" (
    echo [!] .env file not found. Creating from example...
    if exist ".env.example" (
        copy .env.example .env > nul
        echo [OK] Created .env. PLEASE EDIT IT WITH YOUR API KEYS!
    ) else (
        echo [ERR] .env.example missing. Please create .env manually.
        pause
        exit /b 1
    )
)

:: 2. Setup Virtual Environment
if not exist "%VENV_PATH%" (
    echo [*] Creating virtual environment...
    python -m venv venv
    if !ERRORLEVEL! neq 0 (
        echo [ERR] Failed to create venv. Is Python installed?
        pause
        exit /b 1
    )
)

:: 3. Install/Update Dependencies
echo [*] Checking and installing dependencies...
%VENV_PATH%\Scripts\pip install -r requirements.txt
if !ERRORLEVEL! neq 0 (
    echo [ERR] Failed to install dependencies.
    pause
    exit /b 1
)
echo [OK] Dependencies are up to date.

:: 4. Clean up old processes
echo [*] Cleaning up stale bot processes...
taskkill /IM python.exe /F >nul 2>&1
echo [OK] Ready to launch.

:: 5. Launch
echo.
echo [1/2] Launching Bot Daemon (main.py)...
start "OpenClaw Daemon" /min "%PYTHON_EXE%" main.py

echo [2/2] Launching Dashboard UI (dashboard.py)...
echo.
"%STREAMLIT_EXE%" run dashboard.py

pause
