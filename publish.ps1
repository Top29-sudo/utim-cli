# publish.ps1 -- Automated UTIM publication flow

# Prevent accidental runs in incorrect directories
if (-not (Test-Path "package.json") -or -not (Test-Path "pyproject.toml")) {
    Write-Error "Please run this script from the project root directory."
    exit 1
}

# -- 0. Version consistency check ---------------------------------------------
Write-Host ""
Write-Host "Checking version consistency across all files..." -ForegroundColor Cyan

$pyprojectVersion  = (Select-String -Path "pyproject.toml" -Pattern 'version = "(.+)"').Matches[0].Groups[1].Value
$packageVersion    = (Get-Content "package.json" | ConvertFrom-Json).version
$utimPyVersion     = (Select-String -Path "utim_cli\utim.py" -Pattern 'current_ver = "(.+)"').Matches[0].Groups[1].Value
$utimBannerVersion = (Select-String -Path "utim_cli\utim.py" -Pattern '\bv([\d]+\.\d+\.\d+)\[').Matches[0].Groups[1].Value

Write-Host "  pyproject.toml  : $pyprojectVersion"
Write-Host "  package.json    : $packageVersion"
Write-Host "  utim.py banner  : $utimBannerVersion"
Write-Host "  utim.py checker : $utimPyVersion"

$mismatch = $false
foreach ($v in @($packageVersion, $utimPyVersion, $utimBannerVersion)) {
    if ($v -ne $pyprojectVersion) { $mismatch = $true }
}

if ($mismatch) {
    Write-Host ""
    Write-Host "ERROR: Version mismatch detected! All files must have the same version before publishing." -ForegroundColor Red
    Write-Host "Expected: $pyprojectVersion (from pyproject.toml)" -ForegroundColor Red
    Write-Host "Bump versions everywhere and re-run ./publish.ps1" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "OK: All versions match: $pyprojectVersion" -ForegroundColor Green
Write-Host ""

# -- 1. Clean up previous build outputs ---------------------------------------
Write-Host "Cleaning up previous build artifacts..." -ForegroundColor Cyan
Remove-Item -Path "dist", "build", "*.egg-info", "utim_cli.egg-info" -Recurse -ErrorAction SilentlyContinue

# -- 2. Build Python wheel ----------------------------------------------------
Write-Host "Building Python wheel..." -ForegroundColor Cyan
python -m build --no-isolation
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to build Python wheel."
    exit $LASTEXITCODE
}

# -- 3. Upload to PyPI --------------------------------------------------------
Write-Host "Uploading to PyPI via twine..." -ForegroundColor Cyan
python -m twine upload dist/*
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to upload to PyPI."
    exit $LASTEXITCODE
}

# -- 4. Publish to npm --------------------------------------------------------
Write-Host "Publishing to npm..." -ForegroundColor Cyan
npm publish --access public
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to publish to npm."
    exit $LASTEXITCODE
}


Write-Host ""
Write-Host "SUCCESS: Published v$pyprojectVersion to both PyPI and npm." -ForegroundColor Green
Write-Host ""
