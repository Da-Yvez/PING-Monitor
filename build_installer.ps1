# build_installer.ps1
# Automated build script for Ping Monitor installer

Write-Host "Building Ping Monitor Installer..." -ForegroundColor Green

# Step 1: Build executable
Write-Host "`n[1/3] Building executable..." -ForegroundColor Cyan

# Check for venvwin
$pyinstaller = "pyinstaller"
if (Test-Path ".\venvwin\Scripts\pyinstaller.exe") {
    $pyinstaller = ".\venvwin\Scripts\pyinstaller.exe"
}

& $pyinstaller ping_monitor.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error building executable!" -ForegroundColor Red
    exit 1
}

# Step 2: Test executable
Write-Host "`n[2/3] Testing executable..." -ForegroundColor Cyan
if (Test-Path "dist\Ping Monitor.exe") {
    Write-Host "Executable created successfully!" -ForegroundColor Green
} else {
    Write-Host "Executable not found!" -ForegroundColor Red
    exit 1
}

# Step 3: Build installer
Write-Host "`n[3/3] Building installer..." -ForegroundColor Cyan
$innoSetupPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (Test-Path $innoSetupPath) {
    & $innoSetupPath installer.iss
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error building installer!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Inno Setup not found at: $innoSetupPath" -ForegroundColor Red
    Write-Host "Please install Inno Setup to create the installer (Output will be just the executable for now)" -ForegroundColor Yellow
    # Don't exit with error, just warn
}

Write-Host "`n✅ Build complete!" -ForegroundColor Green
Write-Host "Executable: dist\Ping Monitor.exe" -ForegroundColor Yellow
if (Test-Path "installer_output\PingMonitorSetup.exe") {
    Write-Host "Installer: installer_output\PingMonitorSetup.exe" -ForegroundColor Yellow
}
