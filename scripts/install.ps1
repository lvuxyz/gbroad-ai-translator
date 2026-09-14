# ==============================================================================
# Installer Script for Windows AI Translation Tool
# Installs to %LOCALAPPDATA%\Programs\AITranslator without requiring Admin rights
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host ">>> Dang chuan bi cai dat AI Translator..." -ForegroundColor Cyan

# 1. Terminate running instances
$running = Get-Process -Name "AITranslator" -ErrorAction SilentlyContinue
if ($running) {
    Write-Host ">>> Dang dong phien ban AITranslator cu dang chay..." -ForegroundColor Yellow
    $running | Stop-Process -Force
    Start-Sleep -Seconds 1
}

# 2. Paths
$sourceDir = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path "$sourceDir\AITranslator.exe")) {
    $sourceDir = "$sourceDir\dist"
}

$installDir = "$env:LOCALAPPDATA\Programs\AITranslator"
$desktopDir = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$startMenuDir = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Programs)

Write-Host ">>> Thu muc cai dat: $installDir" -ForegroundColor Gray

# 3. Create destination directory & copy files
if (-not (Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}
$assetsDir = "$installDir\assets"
if (-not (Test-Path $assetsDir)) {
    New-Item -ItemType Directory -Path $assetsDir -Force | Out-Null
}

$exeSource = "$sourceDir\AITranslator.exe"
if (-not (Test-Path $exeSource)) {
    Write-Error "Khong tim thay file $exeSource! Hay chac chan da bien dich thanh cong."
    exit 1
}

Copy-Item -Path $exeSource -Destination "$installDir\AITranslator.exe" -Force
Write-Host ">>> Da sao chep file thuc thi AITranslator.exe" -ForegroundColor Green

# Copy assets if available
$iconSource = Join-Path (Split-Path -Parent $PSScriptRoot) "assets\icon.ico"
if (Test-Path $iconSource) {
    Copy-Item -Path $iconSource -Destination "$assetsDir\icon.ico" -Force
}

# 4. Create Shortcuts (Desktop & Start Menu) using WScript.Shell
$wsh = New-Object -ComObject WScript.Shell

# Desktop Shortcut
$desktopShortcutPath = "$desktopDir\AI Translator.lnk"
$shortcut = $wsh.CreateShortcut($desktopShortcutPath)
$shortcut.TargetPath = "$installDir\AITranslator.exe"
$shortcut.WorkingDirectory = $installDir
$shortcut.Description = "AI Translator - Gboard Translate for Windows"
if (Test-Path "$assetsDir\icon.ico") {
    $shortcut.IconLocation = "$assetsDir\icon.ico,0"
}
$shortcut.Save()
Write-Host ">>> Da tao bieu tuong Desktop: $desktopShortcutPath" -ForegroundColor Green

# Start Menu Shortcut
$startMenuShortcutPath = "$startMenuDir\AI Translator.lnk"
$smShortcut = $wsh.CreateShortcut($startMenuShortcutPath)
$smShortcut.TargetPath = "$installDir\AITranslator.exe"
$smShortcut.WorkingDirectory = $installDir
$smShortcut.Description = "AI Translator - Gboard Translate for Windows"
if (Test-Path "$assetsDir\icon.ico") {
    $smShortcut.IconLocation = "$assetsDir\icon.ico,0"
}
$smShortcut.Save()
Write-Host ">>> Da tao bieu tuong Start Menu: $startMenuShortcutPath" -ForegroundColor Green

# 5. Enable Run at Windows Startup in Registry
$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Set-ItemProperty -Path $regPath -Name "AITranslator" -Value "`"$installDir\AITranslator.exe`" --tray"
Write-Host ">>> Da thiet lap tu dong khoi dong cung Windows" -ForegroundColor Green

# 6. Launch Application
Write-Host ">>> Dang khoi chay AI Translator..." -ForegroundColor Cyan
Start-Process -FilePath "$installDir\AITranslator.exe"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "           CAI DAT HOAN TAT THANH CONG!                 " -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host "Cach dung:" -ForegroundColor Yellow
Write-Host "1. Boi den van ban trong bat ky ung dung nao." -ForegroundColor White
Write-Host "2. Nhan to hop phim tat: Ctrl + Shift + T" -ForegroundColor White
Write-Host "3. Van ban se duoc AI tu dong dich va thay the ngay!" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Green
