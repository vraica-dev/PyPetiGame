# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-file build spec for PyPetiGame.

Build locally:
    pip install "pyinstaller>=6"
    pyinstaller pypetigame.spec

Output: dist/pypetigame (Linux one-file binary, local build only).
No releases are created or published from this spec.

Bundled data:
  - static/  (images, audio, Luckiest Guy font) -> extracted to sys._MEIPASS
               and found via the frozen-aware BASE_DIR helper in game.py
Not bundled:
  - scoreboard_db/scores_db — SQLite needs a writable, persistent location,
    so frozen builds store it per-user (see game._default_db_path):
    Linux ~/.local/share/pypetigame/, macOS ~/Library/Application
    Support/PyPetiGame/, Windows %APPDATA%/PyPetiGame/.
"""

a = Analysis(
    ['run_game.py'],
    pathex=[],
    binaries=[],
    datas=[('static', 'static')],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name='pypetigame',
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
