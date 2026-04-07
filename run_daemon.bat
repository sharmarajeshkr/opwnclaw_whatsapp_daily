@echo off
title OpenClaw Bot Daemon
echo --------------------------------------------------
echo      OpenClaw Multi-User Bot Daemon
echo --------------------------------------------------
echo.
echo Starting process...
.\venv\Scripts\python.exe main.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] The bot process exited with error code %ERRORLEVEL%.
    pause
)
