@echo off
title OpenClaw Dashboard
echo --------------------------------------------------
echo      OpenClaw Multi-User Bot Dashboard
echo --------------------------------------------------
echo.
echo Starting Streamlit...
.\venv\Scripts\streamlit.exe run app.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] The dashboard process exited with error code %ERRORLEVEL%.
    pause
)
