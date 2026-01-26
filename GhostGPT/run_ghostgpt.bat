@echo off
chcp 65001 >nul
echo ========================================
echo 🤖 GHOSTGPT: THE GOLDEN MASTER
echo ========================================
echo.

echo Activating virtual environment...
call ..\venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt

echo Starting GhostGPT...
python main.py

pause