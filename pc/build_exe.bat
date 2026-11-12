@echo off
title SunDroid - Build Standalone Windows EXE
cd /d "%~dp0"

echo ========================================================
echo        SunDroid - Build Standalone Windows EXE
echo ========================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak ditemukan di sistem Windows kamu!
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

echo [*] Memeriksa dependensi dan menginstall PyInstaller...
pip install -r requirements.txt pyinstaller

echo.
echo [*] Memulai proses compile ke SunDroid.exe...
echo [*] Mohon tunggu beberapa saat...
pyinstaller --noconfirm --onefile --windowed --name "SunDroid" --collect-all pygame client.py

if exist dist\SunDroid.exe (
    echo.
    echo ========================================================
    echo [SUKSES] File SunDroid.exe berhasil dibuat!
    echo Lokasi: %~dp0dist\SunDroid.exe
    echo ========================================================
    echo Membuka folder output...
    explorer dist
) else (
    echo.
    echo ========================================================
    echo [ERROR] Gagal membuat SunDroid.exe. Silakan periksa log di atas.
    echo ========================================================
)

pause
