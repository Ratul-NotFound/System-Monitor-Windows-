@echo off
cd /d "%~dp0"
title System Monitor Launcher

echo Checking Python virtual environment...
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

echo Activating virtual environment...
call .venv\Scripts\activate

echo Installing dependencies...
pip install -r requirements.txt --quiet

echo Launching widget in background...
start "" .venv\Scripts\pythonw.exe app.py

echo Done!
exit
