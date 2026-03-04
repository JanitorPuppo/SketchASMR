#define MyAppName "DrawTablet ASMR"
#define MyAppVersion "1.0.0"
#define MyAppExeName "DrawTablet ASMR.exe"

[Setup]
AppId={{E3A7B2C1-5D4F-4E6A-9B8C-1F2D3E4A5B6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=installer_output
OutputBaseFilename=DrawTablet_ASMR_Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
SetupIconFile=
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "startupicon"; Description: "Start automatically with Windows"; GroupDescription: "Startup:"

[Files]
Source: "dist\DrawTablet ASMR\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
