# -*- mode: python ; coding: utf-8 -*-

# 说明：PyInstaller 执行 .spec 时并不总是提供 __file__。
# 因此这里用当前工作目录作为“项目根目录”。
# build_exe.bat 已经 cd 到脚本所在目录，所以 cwd 就是项目根目录。

import os
from pathlib import Path

PROJECT_DIR = Path(os.getcwd()).resolve()
ICON_FILE = 'icon.ico'
ICON_PATH = str(PROJECT_DIR / ICON_FILE)


a = Analysis(
    ['image_to_video_converter.py'],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    # 将 icon.ico 打包到 dist 根目录，供运行时 root.iconbitmap 使用
    datas=[(ICON_PATH, '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyinstaller_tkinter_runtime_hook.py'],
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
    name='image_to_video_converter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_PATH,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='image_to_video_converter',
)
