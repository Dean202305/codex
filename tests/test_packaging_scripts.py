from pathlib import Path


def test_macos_build_script_creates_dmg_output() -> None:
    script = Path("scripts/build_macos_app.sh").read_text(encoding="utf-8")

    assert "DMG_PATH" in script
    assert "hdiutil create" in script
    assert "本地安装包" in script
    assert "packaging/runtime" in script
    assert "ALLOW_MISSING_LOCAL_RUNTIME" in script


def test_runtime_readme_documents_required_local_model_binaries() -> None:
    readme = Path("packaging/runtime/README.md").read_text(encoding="utf-8")

    assert "macos-arm64/llama-server" in readme
    assert "macos-x64/llama-server" in readme
    assert "windows-x64/llama-server.exe" in readme


def test_windows_build_script_and_spec_exist() -> None:
    script = Path("scripts/build_windows_app.ps1").read_text(encoding="utf-8")
    spec = Path("packaging/windows/resume_screening_windows.spec").read_text(encoding="utf-8")

    assert "PyInstaller" in script
    assert "windows-x64" in script
    assert "ALLOW_MISSING_LOCAL_RUNTIME" in script
    assert "desktop_entry.py" in spec
    assert '"packaging" / "runtime"' in spec
    assert "runtime_datas" in spec
    assert "binaries=[]" in spec.replace(" ", "")
    assert "resume_screening" in spec


def test_windows_portable_workflow_uploads_zip_artifact() -> None:
    workflow = Path(".github/workflows/build-windows-portable.yml").read_text(encoding="utf-8")

    assert "windows-latest" in workflow
    assert "llama-server.exe" in workflow
    assert "scripts\\build_windows_app.ps1" in workflow or "scripts/build_windows_app.ps1" in workflow
    assert "actions/upload-artifact" in workflow
    assert "小A简历筛选-windows-x64.zip" in workflow
