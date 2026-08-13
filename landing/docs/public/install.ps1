# UTIM CLI Windows PowerShell Installation Script
$ErrorActionPreference = 'Stop'

Write-Host "🚀 Installing UTIM CLI for Windows..." -ForegroundColor Cyan

# Check Node.js / NPM availability
$npmExists = Get-Command npm -ErrorAction SilentlyContinue

if ($npmExists) {
    Write-Host "📦 Found Node.js npm. Installing @emend-ai/utim globally..." -ForegroundColor Green
    npm install -g @emend-ai/utim
} else {
    $pythonExists = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonExists) {
        Write-Host "🐍 Installing UTIM CLI via Python pip..." -ForegroundColor Green
        python -m pip install utim
    } else {
        Write-Host "❌ Error: Neither Node.js (npm) nor Python (pip) was found on your system." -ForegroundColor Red
        Write-Host "Please install Node.js 18+ (https://nodejs.org) or Python 3.9+ and try again." -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "`n✔ UTIM CLI installation complete! Run 'utim' to start." -ForegroundColor Green
