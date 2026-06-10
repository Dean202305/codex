#define MyAppName "小A简历筛选"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "小A科技"
#define MyAppExeName "小A简历筛选.exe"
#define RepoRoot "..\.."
#define AppSource RepoRoot + "\dist\小A简历筛选"

[Setup]
AppId={{8B6B3C4A-81F0-4F7E-94FA-90F1A934C75A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist
OutputBaseFilename=小A简历筛选-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："; Flags: unchecked
Name: "webview2"; Description: "检测并安装 Microsoft Edge WebView2 Runtime"; GroupDescription: "运行环境："; Flags: checkedonce

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "install-webview2.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\install-webview2.ps1"""; Description: "检测并安装 Microsoft Edge WebView2 Runtime"; Flags: runhidden waituntilterminated; Tasks: webview2
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent
