@echo off
chcp 65001 >nul
title xDownloader
cd /d "%~dp0"

echo ====================================
echo              xDownloader
echo ====================================
echo.
echo Starting the local web UI...
echo If this is your first run, copy config.example.json to config.json first.
echo.

python xdownloader.py

if %errorlevel% neq 0 (
    echo.
    echo xDownloader failed to start. Make sure Python is installed and run:
    echo   pip install -r requirements.txt
    echo.
    pause
)
