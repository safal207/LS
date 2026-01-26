@echo off
cls
echo ========================================
echo 🤖 GHOST DASHBOARD: INTEGRATED SYSTEM
echo ========================================
echo Starting full GhostGPT with Glass UI...
echo.

cd /d "%~dp0"
call ..\venv\Scripts\activate

echo Activating integrated system...
python integrated_system.py

echo.
echo System shutdown complete.
pause