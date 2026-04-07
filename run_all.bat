@echo off
title OpenClaw All-in-One Launcher
echo --------------------------------------------------
echo      OpenClaw — All-in-One Launcher
echo --------------------------------------------------
echo.

:: Start the Bot Daemon in a separate window
echo [1/2] Launching Bot Daemon (main.py)...
start "OpenClaw Daemon" /min .\venv\Scripts\python.exe main.py

:: Start the Streamlit Dashboard in the current window
echo [2/2] Launching Dashboard UI (app.py)...
.\venv\Scripts\streamlit.exe run app.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] The dashboard process exited with error code %ERRORLEVEL%.
    pause
)
