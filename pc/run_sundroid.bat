@echo off
title SunDroid - Ultra Low Latency Android Remote (PC Client)
cd /d "%~dp0"

echo ========================================================
echo        SunDroid PC - Remote Android Satset
echo ========================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak ditemukan di Windows kamu!
    echo Silakan install Python 3.10 / 3.11 / 3.12 dari python.org
    echo Pastikan centang "Add Python to PATH" saat instalasi.
    pause
    exit /b 1
)

if not exist venv (
    echo [*] Menyiapkan virtual environment...
    python -m venv venv
)

echo [*] Mengaktifkan virtual environment...
call venv\Scripts\activate.bat

echo [*] Memeriksa dependensi (Pygame, PyAV, Pillow)...
pip install -r requirements.txt

echo.
echo ========================================================
echo [OK] Menjalankan SunDroid PC Client...
echo ========================================================
python client.py

pause
