$ErrorActionPreference = "Stop"

$WebView2ClientGuid = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
$BootstrapperUrl = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
$BootstrapperPath = Join-Path $env:TEMP "MicrosoftEdgeWebview2Setup.exe"

function Test-WebView2Installed {
    $RegistryPaths = @(
        "HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$WebView2ClientGuid",
        "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$WebView2ClientGuid",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\$WebView2ClientGuid"
    )

    foreach ($Path in $RegistryPaths) {
        try {
            $Item = Get-ItemProperty -Path $Path -ErrorAction Stop
            if ($Item.pv -and $Item.pv -ne "0.0.0.0") {
                return $true
            }
        } catch {
            continue
        }
    }
    return $false
}

if (Test-WebView2Installed) {
    Write-Host "Microsoft Edge WebView2 Runtime already installed."
    exit 0
}

Write-Host "Downloading Microsoft Edge WebView2 Runtime..."
Invoke-WebRequest -Uri $BootstrapperUrl -OutFile $BootstrapperPath -UseBasicParsing

Write-Host "Installing Microsoft Edge WebView2 Runtime..."
$Process = Start-Process -FilePath $BootstrapperPath -ArgumentList "/silent", "/install" -Wait -PassThru
if ($Process.ExitCode -ne 0 -and -not (Test-WebView2Installed)) {
    throw "Microsoft Edge WebView2 Runtime installer failed with exit code $($Process.ExitCode)."
}

if (-not (Test-WebView2Installed)) {
    throw "Microsoft Edge WebView2 Runtime was not detected after installation."
}

Write-Host "Microsoft Edge WebView2 Runtime installed."
