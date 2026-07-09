@echo off
chcp 65001 >nul
title Twitter (X) Downloader

cd /d "%~dp0"

echo ====================================
echo    Twitter (X) Media Downloader
echo ====================================
echo.

echo [1/3] Checking Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH
    echo install from: https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version
echo.

echo [2/3] Installing dependencies...
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo WARNING: Some dependencies may not have installed correctly
)
echo.

echo [3/3] Starting downloader...
echo.
echo Usage:
echo   python main.py download    - Download media
echo   python main.py tag         - Search by tag
echo   python main.py text        - Text-only download
echo.
echo Edit config.json to set your users, cookie, proxy etc.
echo ====================================
echo.

python main.py download

echo.
echo Done! Press any key to exit...
pause >nul
