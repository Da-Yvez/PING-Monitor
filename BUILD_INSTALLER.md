# Building the Ping Monitor Installer

This guide walks you through building a professional Windows installer for Ping Monitor.

## Prerequisites

### 1. Python Dependencies
Ensure you have all required packages installed:
```powershell
pip install -r requirements.txt
pip install pyinstaller
```

### 2. Inno Setup
Download and install Inno Setup (free):
- Visit: https://jrsoftware.org/isdl.php
- Download: Inno Setup 6.x (latest version)
- Install with default settings

## Build Process

### Step 1: Build the Executable

Run PyInstaller with the spec file:
```powershell
pyinstaller ping_monitor.spec
```

This will:
- Create a standalone executable in `dist\Ping Monitor.exe`
- Bundle all assets (logo, icon, QR code)
- Include version information and Yvexa branding
- Take approximately 1-2 minutes

**Expected Output:**
```
Building EXE from EXE-00.toc completed successfully.
```

### Step 2: Test the Executable

Before creating the installer, test the executable:
```powershell
.\dist\"Ping Monitor.exe"
```

**Verify:**
- ✅ Application launches without errors
- ✅ Yvexa logo appears in taskbar and title bar
- ✅ About dialog shows Yvexa branding
- ✅ Add a host and close the app
- ✅ Reopen and verify the host persists

### Step 3: Build the Installer

Compile the Inno Setup script:
```powershell
# If Inno Setup is in PATH:
iscc installer.iss

# Or use full path:
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

**Expected Output:**
```
Successful compile (X.XX sec). Resulting Setup program filename is:
installer_output\PingMonitorSetup.exe
```

### Step 4: Test the Installer

1. **Run the installer:**
   ```powershell
   .\installer_output\PingMonitorSetup.exe
   ```

2. **Verify installation:**
   - Custom welcome page with Yvexa branding
   - Installation path selection
   - Desktop shortcut option
   - Start Menu shortcuts created

3. **Test the installed application:**
   - Launch from Start Menu
   - Add 2-3 hosts
   - Close and reopen
   - Verify hosts persist

4. **Test uninstallation:**
   - Uninstall via Control Panel
   - Choose to keep data
   - Reinstall
   - Verify hosts are still there

## Distribution

The final installer is located at:
```
installer_output\PingMonitorSetup.exe
```

This single file contains everything needed to install Ping Monitor on any Windows 10+ system.

### File Size
- Executable: ~30-40 MB
- Installer: ~30-40 MB

## Troubleshooting

### PyInstaller Issues

**Error: "Module not found"**
```powershell
pip install --upgrade customtkinter Pillow
```

**Error: "Failed to execute script"**
- Check that all assets (yvexa-logo.png, yvexa-logo.ico, qr.png) exist
- Verify paths in ping_monitor.spec

### Inno Setup Issues

**Error: "Cannot find file"**
- Ensure `dist\Ping Monitor.exe` exists
- Run PyInstaller first (Step 1)

**Error: "ISCC is not recognized"**
- Add Inno Setup to PATH, or use full path to ISCC.exe

## Quick Build Script

For convenience, here's a PowerShell script to build everything:

```powershell
# build_installer.ps1

Write-Host "Building Ping Monitor Installer..." -ForegroundColor Green

# Step 1: Build executable
Write-Host "`n[1/3] Building executable..." -ForegroundColor Cyan
pyinstaller ping_monitor.spec
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
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error building installer!" -ForegroundColor Red
    exit 1
}

Write-Host "`n✅ Build complete!" -ForegroundColor Green
Write-Host "Installer location: installer_output\PingMonitorSetup.exe" -ForegroundColor Yellow
```

Save as `build_installer.ps1` and run:
```powershell
.\build_installer.ps1
```

## Version Updates

To update the version number:

1. **app.py** - Line ~523: Update version string
2. **ping_monitor.spec** - Lines 48-49: Update FileVersion and ProductVersion
3. **installer.iss** - Line 6: Update MyAppVersion

## Support

For issues or questions:
- Website: https://yvexa.dev
- GitHub: Check the repository issues

## Publishing to GitHub

It is best practice **NOT** to commit large executables or installers directly to your git repository. Instead, use **GitHub Releases**.

### 1. Commit Your Code (Without Binaries)
Ensure your `.gitignore` excludes `dist/`, `build/`, and `installer_output/` (already configured).
```bash
git add .
git commit -m "Release v3.0 Professional"
git push origin main
```

### 2. Create a Release
1. Go to your GitHub repository: https://github.com/Da-Yvez/PING-Monitor
2. Click **"Releases"** on the right sidebar (or go to `/releases`).
3. Click **"Draft a new release"**.
4. **Tag version**: `v3.0.0`
5. **Release title**: `Ping Monitor v3.0 Professional`
6. **Description**: List the new features (Custom branding, Installer, Persistence, etc.).

### 3. Upload Assets
Drag and drop the following files into the "Attach binaries..." box:
- `installer_output\PingMonitorSetup.exe` (The Installer - **Recommended**)
- `dist\Ping Monitor.exe` (The Portable Executable - Optional for advanced users)

### 4. Publish
Click **"Publish release"**.

Users can now download the installer directly from the "Assets" section of the release!

---

**Built with ❤️ by Yvexa**
