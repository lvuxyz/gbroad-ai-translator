@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo       CAI DAT AI TRANSLATOR (GBOARD CHO WINDOWS)
echo ========================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"

echo.
pause
