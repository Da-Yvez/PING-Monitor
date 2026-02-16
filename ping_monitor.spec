# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ping_monitor_icon.ico', '.'),
        ('qr.png', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Ping Monitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='ping_monitor_icon.ico',
    version_info={
        'CompanyName': 'Yvexa',
        'FileDescription': 'Ping Monitor - Network Monitoring Tool',
        'FileVersion': '4.0.0.0',
        'InternalName': 'PingMonitor',
        'LegalCopyright': ' 2026 Yvexa. All rights reserved.',
        'OriginalFilename': 'Ping Monitor.exe',
        'ProductName': 'Ping Monitor',
        'ProductVersion': '4.0.0.0',
    }
)
