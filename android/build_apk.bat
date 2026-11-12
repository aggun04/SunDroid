@echo off
title SunDroid - Build Android APK
cd /d "%~dp0"

echo ========================================================
echo        SunDroid - Build Android Host APK
echo ========================================================
echo.

where gradle >nul 2>nul
if %errorlevel% equ 0 (
    echo [*] Menjalankan gradle assembleDebug...
    call gradle assembleDebug
) else (
    echo [INFO] Untuk build APK secara lokal di PC:
    echo 1. Buka folder 'android' ini di Android Studio.
    echo 2. Klik menu: Build -^> Build Bundle(s) / APK(s) -^> Build APK(s).
    echo 3. Selesai! File APK ada di: app\build\outputs\apk\debug\app-debug.apk
    echo.
)

if exist app\build\outputs\apk\debug\app-debug.apk (
    copy /y app\build\outputs\apk\debug\app-debug.apk SunDroid.apk >nul
    echo ========================================================
    echo [SUKSES] File SunDroid.apk berhasil disiapkan!
    echo Lokasi: %~dp0SunDroid.apk
    echo ========================================================
    explorer .
)
pause
