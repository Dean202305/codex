from pathlib import Path


def test_macos_build_script_creates_dmg_output() -> None:
    script = Path("scripts/build_macos_app.sh").read_text(encoding="utf-8")

    assert "DMG_PATH" in script
    assert "hdiutil create" in script
    assert "本地安装包" in script
    assert "packaging/runtime" in script
    assert "ALLOW_MISSING_LOCAL_RUNTIME" in script


def test_macos_build_script_verifies_packaged_app_after_xattr_cleanup() -> None:
    script = Path("scripts/build_macos_app.sh").read_text(encoding="utf-8")

    assert 'chflags -R nohidden "$target"' in script
    assert 'find "$target" -exec xattr -c {} \\;' in script
    assert 'codesign --force --deep --sign - "$PACKAGE_APP_PATH"' in script
    assert 'codesign --verify --deep --strict --verbose=2 "$PACKAGE_APP_PATH"' in script


def test_runtime_readme_documents_required_local_model_binaries() -> None:
    readme = Path("packaging/runtime/README.md").read_text(encoding="utf-8")

    assert "macos-arm64/llama-server" in readme
    assert "macos-x64/llama-server" in readme
    assert "windows-x64/llama-server.exe" in readme
    assert "WebView2" in readme
    assert "user confirms" in readme


def test_windows_build_script_and_spec_exist() -> None:
    script = Path("scripts/build_windows_app.ps1").read_text(encoding="utf-8")
    spec = Path("packaging/windows/resume_screening_windows.spec").read_text(encoding="utf-8")

    assert "[switch]$Installer" in script
    assert "PyInstaller" in script
    assert "windows-x64" in script
    assert "ALLOW_MISSING_LOCAL_RUNTIME" in script
    assert "_internal\\packaging\\runtime" in script
    assert "Windows 包缺少本地模型运行器" in script
    assert "ISCC" in script
    assert "resume_screening_installer.iss" in script
    assert "小A简历筛选-windows-x64-setup.exe" in script
    assert "desktop_entry.py" in spec
    assert '"packaging" / "runtime"' in spec
    assert "runtime_datas" in spec
    assert "binaries=[]" in spec.replace(" ", "")
    assert "resume_screening" in spec


def test_windows_installer_script_checks_webview2_and_installs_app() -> None:
    installer = Path("packaging/windows/resume_screening_installer.iss").read_text(encoding="utf-8")
    webview2 = Path("packaging/windows/install-webview2.ps1").read_text(encoding="utf-8")

    assert "OutputBaseFilename=小A简历筛选-windows-x64-setup" in installer
    assert "小A简历筛选.exe" in installer
    assert "recursesubdirs" in installer
    assert "install-webview2.ps1" in installer
    assert "Microsoft Edge WebView2 Runtime" in installer
    assert "runhidden" in installer
    assert "waituntilterminated" in installer
    assert "MicrosoftEdgeWebview2Setup.exe" in webview2
    assert "https://go.microsoft.com/fwlink/p/?LinkId=2124703" in webview2
    assert "Test-WebView2Installed" in webview2


def test_windows_workflow_uploads_zip_and_installer_artifacts() -> None:
    workflow = Path(".github/workflows/build-windows-portable.yml").read_text(encoding="utf-8")

    assert "windows-latest" in workflow
    assert "llama-server.exe" in workflow
    assert "Verify Windows portable package" in workflow
    assert "Install Inno Setup" in workflow
    assert "packaging/runtime/windows-x64/llama-server.exe" in workflow
    assert "scripts\\build_windows_app.ps1" in workflow or "scripts/build_windows_app.ps1" in workflow
    assert "-Installer" in workflow
    assert "actions/upload-artifact" in workflow
    assert "小A简历筛选-windows-x64.zip" in workflow
    assert "小A简历筛选-windows-x64-setup.exe" in workflow
