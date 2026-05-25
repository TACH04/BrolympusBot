@echo off
title Brolympus Agent Compiler
:: Force current directory to be the directory containing this batch file
cd /d "%~dp0"

echo ===================================================
echo   Brolympus Agent Executable Builder (Windows)
echo ===================================================
echo.

:: 1. Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your system's PATH.
    echo.
    echo Opening the Python download page in your browser...
    start https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Make sure to check the box "Add Python to PATH" during installation!
    echo After installing Python, please close this window and run build_agent.bat again.
    echo.
    pause
    exit /b
)

:: 2. Upgrade pip and install requirements directly (eliminates requirements.txt requirement)
echo [*] Installing/upgrading required libraries...
python -m pip install --upgrade pip
pip install pystray>=0.19.4 mss>=9.0.1 Pillow>=10.2.0 requests>=2.31.0 plyer>=2.1.0 pyinstaller>=6.4.0
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to install required packages. Please check your internet connection.
    pause
    exit /b
)

:: 3. Check if agent.py exists in the current folder
if not exist "agent.py" (
    echo.
    echo [ERROR] agent.py was not found in this folder!
    echo Please make sure build_agent.bat and agent.py are in the same folder.
    echo.
    pause
    exit /b
)

:: 3.5 Ask for Jetson Tailscale IP to bake into the executable
echo.
echo ===================================================
echo   PRE-CONFIGURE JETSON IP (For Friends)
echo ===================================================
echo To make this seamless for your friends, you can bake your Jetson's
echo Tailscale IP address directly into the compiled executable so they 
echo don't have to configure it manually.
echo.
set /p jetson_ip="Enter your Jetson's Tailscale IP or MagicDNS FQDN (e.g. ubuntu.xxxx.ts.net) [recommended]: "

if not "%jetson_ip%"=="" (
    echo.
    echo [*] Baking http://%jetson_ip%:5002 into agent.py...
    python -c "c=open('agent.py','r',encoding='utf-8').read(); c=c.replace('DEFAULT_SERVER_URL = ' + chr(34) + 'http://127.0.0.1:5002' + chr(34), 'DEFAULT_SERVER_URL = ' + chr(34) + 'http://%jetson_ip%:5002' + chr(34)); open('agent.py','w',encoding='utf-8').write(c)"
)

:: 4. Build executable with PyInstaller
echo.
echo [*] Compiling agent.py into a standalone executable (BrolympusAgent.exe)...
echo [*] This might take a minute...
python -m PyInstaller --onefile --noconsole --name "BrolympusAgent" agent.py

:: 4.5 Revert agent.py changes to keep source code clean
if not "%jetson_ip%"=="" (
    echo [*] Restoring agent.py to default...
    python -c "c=open('agent.py','r',encoding='utf-8').read(); c=c.replace('DEFAULT_SERVER_URL = ' + chr(34) + 'http://%jetson_ip%:5002' + chr(34), 'DEFAULT_SERVER_URL = ' + chr(34) + 'http://127.0.0.1:5002' + chr(34)); open('agent.py','w',encoding='utf-8').write(c)"
)

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
echo   dist\BrolympusAgent.exe
echo.
echo You can distribute this BrolympusAgent.exe file
echo directly to your friends!
echo.
pause
