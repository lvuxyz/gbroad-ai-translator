@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo       Building Windows AI Translation Tool (EXE)
echo ========================================================
echo.

:: Check Python installation
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    pause
    exit /b 1
)

:: Install requirements
echo [1/3] Verifying and installing dependencies...
python -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)

:: Ensure icon assets exist
echo [2/3] Verifying assets...
if not exist assets\icon.ico (
    python -c "from PIL import Image, ImageDraw, ImageFont; from pathlib import Path; p = Path('assets'); p.mkdir(exist_ok=True); img = Image.new('RGBA', (256, 256), color=(0,0,0,0)); draw = ImageDraw.Draw(img); draw.rounded_rectangle([10, 10, 246, 246], radius=50, fill=(14, 116, 144), outline=(6, 182, 212), width=10); img.save('assets/icon.png'); img.save('assets/icon.ico')"
)

:: Build executable with PyInstaller
echo [3/3] Building AITranslator.exe with PyInstaller...
pyinstaller --clean AITranslator.spec

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b 1
)

echo.
echo ========================================================
echo [SUCCESS] Build completed successfully!
echo Executable located at: dist\AITranslator.exe
echo ========================================================
echo.
pause
