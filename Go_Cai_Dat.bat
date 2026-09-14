@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo          GO CAI DAT AI TRANSLATOR
echo ========================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\uninstall.ps1"

echo.
pause
