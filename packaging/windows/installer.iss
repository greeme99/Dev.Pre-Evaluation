; Inno Setup 6 Installer Script for Dev.Pre-Evaluation (TC-106)
; Standard Windows 10/11 64-bit installer with lowest required privileges (per-user by default)

#define MyAppName "Dev.Pre-Evaluation"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Engineering Design Team"
#define MyAppURL "https://github.com/greeme99/Dev.Pre-Evaluation"
#define MyAppExeName "DevPreReview.exe"

[Setup]
AppId={{E5D9F284-B831-4B9F-83C3-8B3FA8F83A20}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\DevPreReview
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=DevPreReview-Setup-x64
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
UninstallDisplayName={#MyAppName}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Dist output from PyInstaller
Source: "..\..\dist\DevPreReview\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Only delete files installed in {app}. Do NOT delete user database in %LOCALAPPDATA%\DevPreReview
Type: filesandordirs; Name: "{app}"

[Code]
// Custom Inno Setup script logic ensuring running instances are closed before install
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
