# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
project_root = Path(SPECPATH).resolve().parents[1]

# Collect all hidden imports for FastAPI, SQLAlchemy, Alembic, and parsers
hidden_imports = [
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
    "alembic",
    "sqlalchemy.sql.default_comparator",
    "cryptography",
    "argon2",
    "openpyxl",
    "fitz",
    "ezdxf",
    "qdrant_client",
] + collect_submodules("dev_pre_review")

datas = [
    (str(project_root / "apps" / "web" / "dist"), "web/dist"),
    (str(project_root / "apps" / "api" / "migrations"), "migrations"),
    (str(project_root / "packaging" / "windows" / "models.json"), "packaging/windows"),
] + collect_data_files("alembic")

a = Analysis(
    [str(project_root / "apps" / "api" / "src" / "dev_pre_review" / "launcher.py")],
    pathex=[str(project_root / "apps" / "api" / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
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
    name="DevPreReview",
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
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DevPreReview",
)
