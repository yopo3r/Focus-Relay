; Instalador de Windows (Inno Setup 6). Se ejecuta desde build_windows.bat o el workflow de GitHub.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
[Setup]
AppName=Focus Relay
AppVersion={#AppVersion}
AppPublisher=Focus Relay
DefaultDirName={autopf}\Focus Relay
DefaultGroupName=Focus Relay
UninstallDisplayIcon={app}\FocusRelay.exe
SetupIconFile=..\assets\icon.ico
OutputDir=..\dist
OutputBaseFilename=FocusRelay-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "dutch"; MessagesFile: "compiler:Languages\Dutch.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked
[Files]
Source: "..\dist\FocusRelay\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
[Icons]
Name: "{group}\Focus Relay"; Filename: "{app}\FocusRelay.exe"
Name: "{autodesktop}\Focus Relay"; Filename: "{app}\FocusRelay.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\FocusRelay.exe"; Description: "{cm:LaunchProgram,Focus Relay}"; Flags: nowait postinstall skipifsilent
