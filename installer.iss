; Inno Setup script: makes ChurchRadio-Studio-Setup.exe.
;
; Built by .github/workflows/release.yml after PyInstaller. Run by hand with:
;   iscc /DAppVersion=1.0.0 installer.iss
; It expects:
;   dist\ChurchRadio-Studio\   the PyInstaller one-folder build
;   build\ffmpeg\              ffmpeg.exe, ffprobe.exe and the ffmpeg license (LGPL build)
;   assets\icon.ico            the app icon
;   LICENSE                    ChurchRadio Studio's own license (shown during setup)
;   build\licenses\            THIRD-PARTY-LICENSES.txt (tools/third_party_licenses.py)
;
; The program goes to Program Files (or the user's own programs folder if they choose
; "Install for me only"). The user's settings, song catalog and history are NOT in the program
; folder: they live in %APPDATA%\ChurchRadio Studio, and the speech models in
; C:\ProgramData\ChurchRadio Studio\models. Uninstalling leaves both, so a reinstall or an
; update keeps everything.
;
; An update normally installs into the folder of the existing installation. If that folder is
; still named after the app's earlier name, the update installs into a "ChurchRadio Studio"
; folder next to it instead and removes the old folder (see [Code]).

#define AppName "ChurchRadio Studio"
#define AppExe "ChurchRadio-Studio.exe"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; Never change AppId: Windows uses it to recognise an update of the same program.
AppId={{1C9F0112-E6A3-47EE-AA4A-5B5EADD57CF0}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Leaven Labs
AppPublisherURL=https://leavenlabs.org
AppCopyright=Copyright (c) 2026 Aaron Steger. MIT License.
LicenseFile=LICENSE
DefaultDirName={code:GetDefaultDir}
UsePreviousAppDir=no
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UsePreviousGroup=no
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=dist
OutputBaseFilename=ChurchRadio-Studio-Setup
SetupIconFile=assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "dist\ChurchRadio-Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "build\ffmpeg\*"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE"; DestDir: "{app}\licenses"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "build\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion

[InstallDelete]
; An update replaces the whole program folder content (old libraries never mix with new ones).
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName} now"; Flags: nowait postinstall skipifsilent

[Code]
const
  UninstKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{1C9F0112-E6A3-47EE-AA4A-5B5EADD57CF0}_is1';
  OldFolderName = 'KNAF Broadcast Builder';

var
  OldDir: String;

// The folder of the existing installation, or '' if there is none.
function PreviousAppDir(): String;
var
  Root: Integer;
begin
  Result := '';
  if IsAdminInstallMode() then
    Root := HKLM64
  else
    Root := HKCU;
  if not RegQueryStringValue(Root, UninstKey, 'Inno Setup: App Path', Result) then
    Result := '';
  Result := RemoveBackslashUnlessRoot(Result);
end;

// Where to install: the existing installation's folder, except that a folder still named after
// the earlier name is swapped for a "ChurchRadio Studio" folder in the same place.
function GetDefaultDir(Param: String): String;
var
  Prev: String;
begin
  Prev := PreviousAppDir();
  if Prev = '' then
    Result := ExpandConstant('{autopf}\{#AppName}')
  else if CompareText(ExtractFileName(Prev), OldFolderName) = 0 then
  begin
    OldDir := Prev;
    Result := AddBackslash(ExtractFileDir(Prev)) + '{#AppName}';
  end
  else
    Result := Prev;
end;

// After an update into the new folder, remove the old program folder. Only a folder that holds
// an Inno Setup uninstaller is removed, so nothing but an old program folder is ever deleted.
// The user's settings and the speech models live elsewhere and are not touched.
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (OldDir <> '') and
     (CompareText(OldDir, RemoveBackslashUnlessRoot(ExpandConstant('{app}'))) <> 0) and
     FileExists(AddBackslash(OldDir) + 'unins000.exe') then
    DelTree(OldDir, True, True, True);
end;
