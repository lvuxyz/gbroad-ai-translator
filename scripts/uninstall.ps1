# ==============================================================================
# Uninstaller Script for Windows AI Translation Tool
# Cleanly removes shortcuts, registry autostart, and installed files
# ==============================================================================

Write-Host ">>> Dang go cai dat AI Translator..." -ForegroundColor Cyan

# 1. Close running process
$running = Get-Process -Name "AITranslator" -ErrorAction SilentlyContinue
if ($running) {
    Write-Host ">>> Dang dong tien trinh AITranslator..." -ForegroundColor Yellow
    $running | Stop-Process -Force
    Start-Sleep -Seconds 1
}

# 2. Delete Shortcuts
$desktopDir = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$startMenuDir = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Programs)

$desktopShortcut = "$desktopDir\AI Translator.lnk"
if (Test-Path $desktopShortcut) {
    Remove-Item -Path $desktopShortcut -Force
    Write-Host ">>> Da xoa phim tat Desktop" -ForegroundColor Green
}

$startMenuShortcut = "$startMenuDir\AI Translator.lnk"
if (Test-Path $startMenuShortcut) {
    Remove-Item -Path $startMenuShortcut -Force
    Write-Host ">>> Da xoa phim tat Start Menu" -ForegroundColor Green
}

# 3. Remove Registry Startup
$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
if (Get-ItemProperty -Path $regPath -Name "AITranslator" -ErrorAction SilentlyContinue) {
    Remove-ItemProperty -Path $regPath -Name "AITranslator" -ErrorAction SilentlyContinue
    Write-Host ">>> Da huy tu dong khoi dong cung Windows" -ForegroundColor Green
}

# 4. Remove Installation Directory
$installDir = "$env:LOCALAPPDATA\Programs\AITranslator"
if (Test-Path $installDir) {
    Remove-Item -Path $installDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host ">>> Da xoa thu muc chuong trinh: $installDir" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "        DA GO CAI DAT AI TRANSLATOR HOAN TAT!           " -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
