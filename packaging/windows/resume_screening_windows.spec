# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ROOT = Path.cwd()
APP_NAME = "小A简历筛选"

datas = collect_data_files("resume_screening")


def clean_modules(modules):
    return [module for module in modules if " " not in module]


def runtime_binaries():
    # Bundle local model runtimes from packaging/runtime/<platform>/llama-server*.
    runtime_root = ROOT / "packaging" / "runtime"
    if not runtime_root.exists():
        return []
    return [
        (str(path), str(path.parent.relative_to(ROOT)))
        for path in runtime_root.glob("**/llama-server*")
        if path.is_file()
    ]


hiddenimports = (
    clean_modules(collect_submodules("resume_screening"))
    + clean_modules(collect_submodules("uvicorn"))
    + clean_modules(collect_submodules("fastapi"))
    + clean_modules(collect_submodules("pydantic"))
    + clean_modules(collect_submodules("webview"))
)

a = Analysis(
    [str(ROOT / "packaging" / "macos" / "desktop_entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=runtime_binaries(),
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
