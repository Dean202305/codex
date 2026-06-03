param(
    [string]$Python = $env:PYTHON
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

if (-not $Python) {
    $VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path $VenvPython) {
        $Python = $VenvPython
    } else {
        $Python = "python"
    }
}

$RuntimePath = Join-Path $Root "packaging\runtime\windows-x64\llama-server.exe"
if (-not (Test-Path $RuntimePath) -and $env:ALLOW_MISSING_LOCAL_RUNTIME -ne "1") {
    Write-Error "缺少本地模型运行器：$RuntimePath。请按 packaging/runtime/README.md 放置 llama-server.exe，或仅做开发验证时设置 ALLOW_MISSING_LOCAL_RUNTIME=1。"
}

& $Python -m pip install ".[desktop]"

if (Test-Path (Join-Path $Root "web")) {
    npm --prefix web install
    npm --prefix web run build
}

& $Python -m PyInstaller --noconfirm packaging/windows/resume_screening_windows.spec

$AppDir = Join-Path $Root "dist\小A简历筛选"
$ZipPath = Join-Path $Root "dist\小A简历筛选-windows-x64.zip"
if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}
Compress-Archive -Path $AppDir -DestinationPath $ZipPath -Force

Write-Host "已生成：$AppDir"
Write-Host "Windows 可迁移压缩包：$ZipPath"
