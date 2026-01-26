@echo off
echo Setting up Interview Copilot environment...

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
call venv\Scripts\activate

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Install psutil for system monitoring
pip install psutil

echo.
echo Setup complete!
echo.
echo Next steps:
echo 1. Install Ollama from https://ollama.com/
echo 2. Run: ollama pull phi3
echo 3. Install VB-Cable from https://vb-audio.com/Cable/
echo 4. Activate virtual environment: venv\Scripts\activate
echo 5. Run: python main.py
echo.
pause