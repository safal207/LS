@echo off
title Interview Copilot - Ghost Mode
echo ========================================
echo    Interview Copilot - Ghost Mode GUI
echo ========================================
echo.

REM Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo Warning: Virtual environment not found!
    echo Using system Python...
)

REM Check if required packages are installed
echo Checking PyQt6...
python -c "import PyQt6" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyQt6...
    pip install PyQt6
)

REM Run quick GUI test first
echo.
echo Running quick GUI test...
echo Please check:
echo 1. Window appears over other applications
echo 2. Text is readable
echo 3. Window is draggable
echo.
pause

python quick_gui_test.py

echo.
echo Quick test completed.
echo.
echo Now running full Ghost Mode GUI...
echo Make sure:
echo 1. Ollama is running
echo 2. VB-Cable is installed and configured
echo 3. System audio is routed to CABLE Input
echo.
pause

python ghost_gui.py

echo.
echo Ghost Mode GUI closed.
pause