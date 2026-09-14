@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo ========================================================
echo       TẠO GÓI PHÁT HÀNH DỄ SỬ DỤNG CHO WINDOWS
echo ========================================================
echo.

:: 1. Check if dist\AITranslator.exe exists
if not exist "dist\AITranslator.exe" (
    echo [1/3] Chưa tìm thấy file dist\AITranslator.exe, đang tiến hành build...
    call build.bat
) else (
    echo [1/3] Đã có file dist\AITranslator.exe
)

:: 2. Create release folder structure
echo [2/3] Đang đóng gói thư mục release...
if exist "release" rmdir /s /q "release"
mkdir "release\AITranslator"
mkdir "release\AITranslator\assets"
mkdir "release\AITranslator\scripts"

copy /y "dist\AITranslator.exe" "release\AITranslator\" >nul
copy /y "Cai_Dat.bat" "release\AITranslator\" >nul
copy /y "Go_Cai_Dat.bat" "release\AITranslator\" >nul
copy /y "HUONG_DAN_NHANH.txt" "release\AITranslator\" >nul
copy /y "assets\icon.ico" "release\AITranslator\assets\" >nul
copy /y "assets\icon.png" "release\AITranslator\assets\" >nul
copy /y "scripts\install.ps1" "release\AITranslator\scripts\" >nul
copy /y "scripts\uninstall.ps1" "release\AITranslator\scripts\" >nul

:: 3. Create ZIP archive
echo [3/3] Đang nén thành file ZIP hoàn chỉnh...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'release\AITranslator\*' -DestinationPath 'release\AITranslator_v1.0_Windows_x64.zip' -Force"

echo.
echo ========================================================
echo [HOÀN TẤT] ĐÃ TẠO GÓI SỬ DỤNG THÀNH CÔNG!
echo.
echo 1. Thư mục chạy ngay:
echo    release\AITranslator\
echo.
echo 2. File nén ZIP chia sẻ cho người dùng khác:
echo    release\AITranslator_v1.0_Windows_x64.zip
echo ========================================================
echo.
