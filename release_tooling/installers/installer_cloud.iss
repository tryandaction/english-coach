; Inno Setup Script for English Coach - Cloud Edition
; This creates a professional Windows installer

#define MyAppName "English Coach (Cloud)"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "English Coach"
#define MyAppURL "https://englishcoach.app"
#define MyAppExeName "english-coach-cloud.exe"
#define MyAppUninstallKey "{B2C3D4E5-F6A7-8901-BCDE-F12345678901}_is1"
#define ProjectRoot "..\.."

[Setup]
; Basic app info
AppId={{B2C3D4E5-F6A7-8901-BCDE-F12345678901}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation directories - use user local app data (no admin needed)
DefaultDirName={localappdata}\English Coach Cloud
DefaultGroupName=English Coach Cloud
DisableProgramGroupPage=yes
; Always use the canonical install dir instead of reusing a previous temp/smoke path.
UsePreviousAppDir=no
; Close a running old version before replacing files.
CloseApplications=yes
RestartApplications=no

; Output settings
OutputDir={#ProjectRoot}\releases
OutputBaseFilename=english-coach-cloud-setup
; SetupIconFile=gui\static\favicon.ico  ; Commented out - no icon file available
Compression=lzma
SolidCompression=yes

; Windows version requirements
MinVersion=10.0
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; UI settings
WizardStyle=modern
DisableWelcomePage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#ProjectRoot}\releases\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectRoot}\releases\README.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectRoot}\releases\README_v2.0.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectRoot}\releases\RELEASE_NOTES_v2.0.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectRoot}\releases\QUICK_START_v2.0.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectRoot}\releases\DEPLOYMENT_CHECKLIST.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectRoot}\releases\PRODUCT_EDITIONS.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectRoot}\releases\使用指南.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectRoot}\releases\.env.template"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectRoot}\releases\.env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectRoot}\releases\cloud_activation_config.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\English Coach"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\English Coach"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  DefaultUserConfig =
    'backend: ""' + #13#10 +
    'api_key: ""' + #13#10 +
    'data_dir: data' + #13#10 +
    'history_retention_days: 30' + #13#10 +
    'user:' + #13#10 +
    '  name: ""' + #13#10 +
    '  target_exam: ""' + #13#10 +
    '  target_exam_date: ""' + #13#10;

function DataDirReviewFlagPath(): string;
begin
  Result := ExpandConstant('{userappdata}\EnglishCoach\pending_data_dir_review.flag');
end;

function UninstallRegSubkey(): string;
begin
  Result := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppUninstallKey}';
end;

function ShouldResetUserConfig(): Boolean;
var
  ConfigPath: string;
  Content: AnsiString;
begin
  ConfigPath := ExpandConstant('{userappdata}\EnglishCoach\config.yaml');
  if not FileExists(ConfigPath) then
  begin
    Result := False;
    exit;
  end;
  if not LoadStringFromFile(ConfigPath, Content) then
  begin
    Result := False;
    exit;
  end;
  Content := AnsiLowerCase(Content);
  Result :=
    (Pos('english_coach_release_smoke_', Content) > 0) or
    ((Pos('\temp\', Content) > 0) and ((Pos('english coach', Content) > 0) or (Pos('english_coach', Content) > 0)));
end;

procedure ResetSuspiciousUserConfig;
var
  ConfigDir, ConfigPath, BackupPath: string;
begin
  if not ShouldResetUserConfig() then
    exit;
  ConfigDir := ExpandConstant('{userappdata}\EnglishCoach');
  ConfigPath := ConfigDir + '\config.yaml';
  BackupPath := ConfigDir + '\config.dev-backup.yaml';
  if FileExists(BackupPath) then
    DeleteFile(BackupPath);
  RenameFile(ConfigPath, BackupPath);
  ForceDirectories(ConfigDir);
  SaveStringToFile(ConfigPath, DefaultUserConfig, False);
end;

procedure RemoveOldShortcuts;
begin
  DelTree(ExpandConstant('{group}'), True, True, True);
  DelTree(ExpandConstant('{userprograms}\English Coach'), True, True, True);
  DelTree(ExpandConstant('{userprograms}\English Coach Cloud'), True, True, True);
  DelTree(ExpandConstant('{userprograms}\English Coach Open Source'), True, True, True);
  DelTree(ExpandConstant('{commonprograms}\English Coach'), True, True, True);
  DelTree(ExpandConstant('{commonprograms}\English Coach Cloud'), True, True, True);
  DelTree(ExpandConstant('{commonprograms}\English Coach Open Source'), True, True, True);
  DeleteFile(ExpandConstant('{autodesktop}\English Coach.lnk'));
  DeleteFile(ExpandConstant('{userdesktop}\English Coach.lnk'));
  DeleteFile(ExpandConstant('{commondesktop}\English Coach.lnk'));
end;

procedure TerminateRunningAppProcesses;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure SplitCommand(const Command: string; var Filename: string; var Params: string);
var
  S: string;
  I: Integer;
begin
  Filename := '';
  Params := '';
  S := Trim(Command);
  if S = '' then
    exit;
  if Copy(S, 1, 1) = '"' then
  begin
    Delete(S, 1, 1);
    I := Pos('"', S);
    if I > 0 then
    begin
      Filename := Copy(S, 1, I - 1);
      Params := Trim(Copy(S, I + 1, MaxInt));
    end
    else
      Filename := S;
  end
  else
  begin
    I := Pos(' ', S);
    if I > 0 then
    begin
      Filename := Copy(S, 1, I - 1);
      Params := Trim(Copy(S, I + 1, MaxInt));
    end
    else
      Filename := S;
  end;
end;

function RemoveRegistryEntry(RootKey: Integer; const SubKey: string): Boolean;
var
  CmdPath, Params: string;
  ResultCode: Integer;
begin
  Result := True;
  if RootKey = HKCU then
  begin
    RegDeleteKeyIncludingSubkeys(RootKey, SubKey);
    exit;
  end;
  CmdPath := ExpandConstant('{cmd}');
  Params := '/C reg delete "HKLM\' + SubKey + '" /f';
  if not ShellExec('runas', CmdPath, Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := False
  else
    Result := ResultCode = 0;
end;

function UninstallPreviousInstall(RootKey: Integer): Boolean;
var
  SubKey, DisplayName, QuietCommand, UninstallCommand, InstallLocation: string;
  Filename, Params: string;
  ResultCode: Integer;
  Prompt: string;
begin
  Result := True;
  SubKey := UninstallRegSubkey();
  if not RegValueExists(RootKey, SubKey, 'DisplayName') then
    exit;

  RegQueryStringValue(RootKey, SubKey, 'DisplayName', DisplayName);
  RegQueryStringValue(RootKey, SubKey, 'InstallLocation', InstallLocation);
  QuietCommand := '';
  UninstallCommand := '';
  RegQueryStringValue(RootKey, SubKey, 'QuietUninstallString', QuietCommand);
  RegQueryStringValue(RootKey, SubKey, 'UninstallString', UninstallCommand);
  if QuietCommand <> '' then
    SplitCommand(QuietCommand, Filename, Params)
  else
  begin
    SplitCommand(UninstallCommand, Filename, Params);
    if Filename <> '' then
      Params := Trim(Params + ' /VERYSILENT /SUPPRESSMSGBOXES /NORESTART');
  end;

  if not WizardSilent then
  begin
    Prompt :=
      'Detected an older installation:' + #13#10 + #13#10 +
      DisplayName + #13#10 +
      InstallLocation + #13#10 + #13#10 +
      'Setup can close the old version, remove it, and then install the new version.' + #13#10 +
      'Your study data in %APPDATA%\EnglishCoach will be preserved.' + #13#10 + #13#10 +
      'Continue?';
    if MsgBox(Prompt, mbConfirmation, MB_YESNO) <> IDYES then
    begin
      Result := False;
      exit;
    end;
  end;

  TerminateRunningAppProcesses;

  if (Filename = '') or (not FileExists(Filename)) then
  begin
    Result := RemoveRegistryEntry(RootKey, SubKey);
    if not Result then
    begin
      if (InstallLocation = '') or (not DirExists(InstallLocation)) then
      begin
        Result := True;
        if not WizardSilent then
          MsgBox(
            'Detected a stale uninstall entry for an older version, but the old files are already gone.' + #13#10 +
            'Setup will continue with the new installation.',
            mbInformation,
            MB_OK
          );
      end;
    end;
    exit;
  end;

  if RootKey = HKCU then
  begin
    if not Exec(Filename, Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      Result := False
    else
      Result := ResultCode = 0;
  end
  else
  begin
    if not ShellExec('runas', Filename, Params, '', SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode) then
      Result := False
    else
      Result := ResultCode = 0;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  NeedsRestart := False;
  if not UninstallPreviousInstall(HKCU) then
  begin
    Result := 'Setup was canceled before removing the previous current-user installation.';
    exit;
  end;
  if not UninstallPreviousInstall(HKLM) then
  begin
    Result := 'Setup could not remove the previous machine-wide installation. Please allow the admin uninstall prompt, then run setup again.';
    exit;
  end;
  Result := '';
end;

procedure MarkDataDirReviewRequired;
var
  ConfigDir: string;
begin
  ConfigDir := ExpandConstant('{userappdata}\EnglishCoach');
  ForceDirectories(ConfigDir);
  SaveStringToFile(DataDirReviewFlagPath(), '{#MyAppVersion}', False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    RemoveOldShortcuts;
    MarkDataDirReviewRequired;
    ResetSuspiciousUserConfig;
  end;
end;

procedure InitializeWizard;
var
  WelcomeLabel: TNewStaticText;
begin
  WelcomeLabel := TNewStaticText.Create(WizardForm);
  WelcomeLabel.Parent := WizardForm.WelcomePage;
  WelcomeLabel.Caption :=
    'This is the Cloud edition of English Coach.' + #13#10 + #13#10 +
    'Includes bundled starter content and built-in vocabulary libraries.' + #13#10 + #13#10 +
    'If this build includes activation settings, you can activate it with a license key.' + #13#10 +
    'Otherwise, configure your own API key and use the offline-capable flows.' + #13#10 + #13#10 +
    'Upgrades preserve your existing study data, custom word books, and settings stored in %APPDATA%\EnglishCoach.';
  WelcomeLabel.AutoSize := True;
  WelcomeLabel.WordWrap := True;
  WelcomeLabel.Top := WizardForm.WelcomeLabel2.Top + WizardForm.WelcomeLabel2.Height + 20;
  WelcomeLabel.Width := WizardForm.WelcomeLabel2.Width;
end;
