# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Sandglass macOS .app (engine binaries optional via runtime/)

from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

datas = [
    (str(root / "static"), "static"),
]

runtime_dir = root / "runtime"
if runtime_dir.is_dir():
    datas.append((str(runtime_dir), "runtime"))

a = Analysis(
    ["run_desktop.py"],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
    ],
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
    [],
    exclude_binaries=True,
    name="Sandglass",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Sandglass",
)

app = BUNDLE(
    coll,
    name="Sandglass.app",
    icon=None,
    bundle_identifier="dev.sandglass.app",
    info_plist={
        "CFBundleName": "Sandglass",
        "CFBundleDisplayName": "Sandglass",
        "CFBundleGetInfoString": "Self-contained agent sandbox desktop app",
        "NSHighResolutionCapable": True,
    },
)
