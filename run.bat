@echo off
title Interview Copilot
echo ========================================
echo    Local Interview Copilot (Ghost Mode)
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Error: Virtual environment not found!
    echo Run setup.bat first to create virtual environment.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if Ollama is running
echo Checking Ollama connection...
python -c "import requests; requests.get('http://localhost:11434/api/tags')" >nul 2>&1
if %errorlevel% neq 0 (
    echo Warning: Cannot connect to Ollama API
    echo Make sure Ollama is running and phi3 model is installed
    echo.
    echo To install phi3 model: ollama pull phi3
    echo.
    pause
)

REM Run setup check
echo Running setup check...
python check_setup.py
echo.

REM Ask user if they want to continue
echo Ready to start Interview Copilot...
echo Make sure:
echo 1. Your system audio output is set to 'CABLE Input'
echo 2. Ollama is running with phi3 model
echo 3. You're ready for the interview
echo.
choice /C YN /M "Start Interview Copilot"

if %errorlevel% equ 2 (
    echo Exiting...
    exit /b 0
)

echo.
echo Starting Interview Copilot...
echo Press Ctrl+C to stop
echo ========================================
echo.

REM Run the main application
python main.py

echo.
echo Interview Copilot stopped.
pause