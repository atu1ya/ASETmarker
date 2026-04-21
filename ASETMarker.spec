# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_dynamic_libs
from PyInstaller.utils.hooks import collect_submodules


ROOT_DIR = Path(__file__).resolve().parent
ICON_PATH = ROOT_DIR / 'assets' / 'ASETMarker.icns'

datas = [('config', 'config'), ('docs', 'docs'), ('assets', 'assets')]
binaries = []
hiddenimports = ['fitz', 'cv2']
datas += collect_data_files('matplotlib')
datas += collect_data_files('docxtpl')
binaries += collect_dynamic_libs('cv2')
hiddenimports += collect_submodules('desktop')
hiddenimports += collect_submodules('src')


a = Analysis(
    ['main_gui.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    [],
    name='ASETMarker',
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ASETMarker',
)

app = BUNDLE(
    coll,
    name='ASETMarker.app',
    icon=str(ICON_PATH) if ICON_PATH.exists() else None,
    bundle_identifier='com.aset.marker',
)
