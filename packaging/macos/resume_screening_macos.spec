# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ROOT = Path.cwd()
APP_NAME = "小A简历筛选"

datas = collect_data_files("resume_screening")


def clean_modules(modules):
    return [module for module in modules if " " not in module]


def runtime_binaries():
    runtime_root = ROOT / "packaging" / "runtime"
    if not runtime_root.exists():
        return []
    return [
        (str(path), str(path.parent.relative_to(ROOT)))
        for path in runtime_root.glob("**/*")
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

app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon=None,
    bundle_identifier="com.xiaoa.resume-screening",
    info_plist={
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "NSHighResolutionCapable": True,
        "NSDocumentsFolderUsageDescription": "用于读取简历、岗位说明书，并写入招聘结果表。",
        "NSDownloadsFolderUsageDescription": "用于读取下载目录中的简历、岗位说明书，并写入招聘结果表。",
        "NSDesktopFolderUsageDescription": "用于读取桌面目录中的简历、岗位说明书，并写入招聘结果表。",
    },
)
