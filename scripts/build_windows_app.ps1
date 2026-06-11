param(
    [string]$Python = $env:PYTHON,
    [switch]$BundleLocalModel,
    [string]$LocalModelPath = $env:LOCAL_QWEN_MODEL_PATH,
    [switch]$Installer
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

function Resolve-InnoSetupCompiler {
    $Candidates = @()
    if ($env:ISCC_PATH) {
        $Candidates += $env:ISCC_PATH
    }
    $Command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($Command) {
        $Candidates += $Command.Source
    }
    if (${env:ProgramFiles(x86)}) {
        $Candidates += (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
    }
    if ($env:ProgramFiles) {
        $Candidates += (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    }
    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path $Candidate)) {
            return $Candidate
        }
    }
    throw "缺少 Inno Setup 编译器 ISCC。请安装 Inno Setup 6，或设置 ISCC_PATH 后重新执行。"
}

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

$BundleModelRequested = $BundleLocalModel -or $env:BUNDLE_LOCAL_MODEL -eq "1"
$DefaultModelFileName = "Qwen3.5-9B-Q4_K_M.gguf"
if (-not $LocalModelPath) {
    $LocalModelPath = Join-Path $Root "packaging\models\qwen\$DefaultModelFileName"
}
if ($BundleModelRequested -and -not (Test-Path $LocalModelPath)) {
    Write-Error "缺少待内置的本地大模型：$LocalModelPath。请设置 LOCAL_QWEN_MODEL_PATH，或将模型放到 packaging\models\qwen\$DefaultModelFileName。"
}

& $Python -m pip install ".[desktop]"

if (Test-Path (Join-Path $Root "web")) {
    npm --prefix web install
    npm --prefix web run build
}

& $Python -m PyInstaller --noconfirm packaging/windows/resume_screening_windows.spec

$AppDir = Join-Path $Root "dist\小A简历筛选"
$RuntimeSource = Join-Path $Root "packaging\runtime"
$RuntimeDest = Join-Path $AppDir "_internal\packaging\runtime"
if (Test-Path $RuntimeSource) {
    New-Item -ItemType Directory -Force $RuntimeDest | Out-Null
    Copy-Item -Path (Join-Path $RuntimeSource "*") -Destination $RuntimeDest -Recurse -Force
}

$BundledRuntimePath = Join-Path $RuntimeDest "windows-x64\llama-server.exe"
if (-not (Test-Path $BundledRuntimePath) -and $env:ALLOW_MISSING_LOCAL_RUNTIME -ne "1") {
    Write-Error "Windows 包缺少本地模型运行器：$BundledRuntimePath"
}

if ($BundleModelRequested) {
    $ModelDestDir = Join-Path $AppDir "_internal\packaging\models\qwen"
    New-Item -ItemType Directory -Force $ModelDestDir | Out-Null
    Copy-Item -Path $LocalModelPath -Destination (Join-Path $ModelDestDir $DefaultModelFileName) -Force
    $BundledModelPath = Join-Path $ModelDestDir $DefaultModelFileName
    if (-not (Test-Path $BundledModelPath)) {
        Write-Error "Windows 包缺少内置本地大模型：$BundledModelPath"
    }
    Write-Host "已内置本地大模型：$BundledModelPath"
}

$ZipPath = Join-Path $Root "dist\小A简历筛选-windows-x64.zip"
if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}
Compress-Archive -Path $AppDir -DestinationPath $ZipPath -Force

Write-Host "已生成：$AppDir"
Write-Host "Windows 可迁移压缩包：$ZipPath"

if ($Installer) {
    $Iscc = Resolve-InnoSetupCompiler
    $InstallerScript = Join-Path $Root "packaging\windows\resume_screening_installer.iss"
    & $Iscc $InstallerScript
    $SetupPath = Join-Path $Root "dist\小A简历筛选-windows-x64-setup.exe"
    if (-not (Test-Path $SetupPath)) {
        Write-Error "Windows 安装包生成失败：$SetupPath"
    }
    Write-Host "Windows 安装包：$SetupPath"
}
