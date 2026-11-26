; GitDesk Windows 原生安装程序（Inno Setup）
; 用户级安装，无需管理员权限；支持安装路径、开始菜单、桌面图标与卸载。
#define MyAppName "GitDesk"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "GitDesk"
#define MyAppURL "https://github.com/xujc985/gitdesk"
#define MyAppExeName "GitDesk.exe"
#define MyAppId "{{6A1E5B6C-4BB2-4B63-9A33-8A7D6E1C0001}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\GitDesk
DefaultGroupName=GitDesk
AllowNoIcons=yes
OutputDir=..\release
OutputBaseFilename=GitDesk-{#MyAppVersion}-windows-x64-setup
SetupIconFile=..\assets\gitdesk.ico
UninstallDisplayIcon={app}\GitDesk.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=no
CloseApplications=force
RestartApplications=no
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\dist\GitDesk\GitDesk.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\GitDesk\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\gitdesk.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\assets\gitdesk.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\assets\gitdesk.svg"; DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
Name: "{group}\GitDesk"; Filename: "{app}\GitDesk.exe"; WorkingDir: "{app}"; IconFilename: "{app}\assets\gitdesk.ico"
Name: "{group}\Uninstall GitDesk"; Filename: "{uninstallexe}"
Name: "{autodesktop}\GitDesk"; Filename: "{app}\GitDesk.exe"; WorkingDir: "{app}"; IconFilename: "{app}\assets\gitdesk.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\GitDesk.exe"; Description: "Launch GitDesk"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 只清理应用产生的文件，不删除用户的仓库或全局 Git 配置。
Type: filesandordirs; Name: "{app}\__pycache__"
