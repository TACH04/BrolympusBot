@echo off
title Brolympus Agent Compiler
echo ===================================================
echo   Brolympus Agent Executable Builder (Windows)
echo ===================================================
echo.

:: 1. Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your system's PATH.
    echo Please download and install Python 3.8+ from https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Make sure to check the box "Add Python to PATH" during installation.
    echo.
    pause
    exit /b
)

:: 2. Upgrade pip and install requirements
echo [*] Installing/upgrading required libraries...
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to install required packages. Please check your internet connection.
    pause
    exit /b
)

:: 3. Build executable with PyInstaller
echo.
echo [*] Compiling agent.py into a standalone executable (BrolympusAgent.exe)...
echo [*] This might take a minute...
pyinstaller --onefile --noconsole --name "BrolympusAgent" agent.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] PyInstaller compilation failed.
    pause
    exit /b
)

echo.
echo ===================================================
echo   SUCCESS! 
echo ===================================================
echo.
echo The compiled executable is located at:
echo   client\dist\BrolympusAgent.exe
echo.
echo You can send this .exe file to your friends!
echo.
pause
