; Ping Monitor - Inno Setup Installer Script
; Created by Yvexa - Premium Web Development & Design Agency
; https://yvexa.dev

#define MyAppName "Ping Monitor"
#define MyAppVersion "3.0"
#define MyAppPublisher "Yvexa"
#define MyAppURL "https://yvexa.dev"
#define MyAppExeName "Ping Monitor.exe"

[Setup]
; App Information
AppId={{8F3A2B1C-9D4E-5F6A-7B8C-9D0E1F2A3B4C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppCopyright=Copyright (C) 2026 Yvexa. All rights reserved.

; Installation Directories
DefaultDirName={autopf}\Yvexa\{#MyAppName}
DefaultGroupName=Yvexa\{#MyAppName}
DisableProgramGroupPage=yes

; Output Configuration
OutputDir=installer_output
OutputBaseFilename=PingMonitorSetup
SetupIconFile=ping_monitor_icon.ico
WizardImageFile=installer_wizard.bmp
WizardSmallImageFile=installer_small.bmp
UninstallDisplayIcon={app}\{#MyAppExeName}

; Compression
Compression=lzma2/max
SolidCompression=yes

; Windows Version
MinVersion=10.0
ArchitecturesInstallIn64BitMode=x64compatible

; Privileges
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Wizard Appearance
WizardStyle=modern
DisableWelcomePage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{group}\Visit Yvexa Website"; Filename: "{#MyAppURL}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  WelcomePage: TWizardPage;

procedure InitializeWizard;
var
  WelcomeLabel: TNewStaticText;
  DescLabel: TNewStaticText;
  CompanyLabel: TLabel;
  WebsiteLabel: TLabel;
begin
  // Custom Welcome Page
  WelcomePage := CreateCustomPage(wpWelcome, 'Welcome to Ping Monitor Setup', 
    'Professional Network Monitoring Tool');
  
  // Welcome message
  WelcomeLabel := TNewStaticText.Create(WelcomePage);
  WelcomeLabel.Parent := WelcomePage.Surface;
  WelcomeLabel.Caption := 'This wizard will guide you through the installation of Ping Monitor,' + #13#10 +
                          'a powerful real-time network monitoring application.';
  WelcomeLabel.Left := 0;
  WelcomeLabel.Top := 20;
  WelcomeLabel.Width := WelcomePage.SurfaceWidth;
  WelcomeLabel.AutoSize := True;
  
  // Features
  DescLabel := TNewStaticText.Create(WelcomePage);
  DescLabel.Parent := WelcomePage.Surface;
  DescLabel.Caption := 'Features:' + #13#10 +
                       '  • Real-time network monitoring' + #13#10 +
                       '  • Live statistics dashboard' + #13#10 +
                       '  • Graphical latency visualization' + #13#10 +
                       '  • Multi-threaded architecture' + #13#10 +
                       '  • Persistent configuration' + #13#10 +
                       '  • CSV export capability';
  DescLabel.Left := 0;
  DescLabel.Top := 80;
  DescLabel.Width := WelcomePage.SurfaceWidth;
  DescLabel.AutoSize := True;
  
  // Company branding
  CompanyLabel := TLabel.Create(WelcomePage);
  CompanyLabel.Parent := WelcomePage.Surface;
  CompanyLabel.Caption := 'Developed by Yvexa';
  CompanyLabel.Font.Style := [fsBold];
  CompanyLabel.Font.Size := 11;
  CompanyLabel.Left := 0;
  CompanyLabel.Top := WelcomePage.SurfaceHeight - 60;
  CompanyLabel.AutoSize := True;
  
  // Website
  WebsiteLabel := TLabel.Create(WelcomePage);
  WebsiteLabel.Parent := WelcomePage.Surface;
  WebsiteLabel.Caption := 'Premium Web Development & Design Agency';
  WebsiteLabel.Font.Color := clGray;
  WebsiteLabel.Left := 0;
  WebsiteLabel.Top := WelcomePage.SurfaceHeight - 40;
  WebsiteLabel.AutoSize := True;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Additional post-install tasks can go here
  end;
end;

function InitializeUninstall(): Boolean;
var
  Response: Integer;
begin
  Response := MsgBox('Do you want to keep your saved host configurations?' + #13#10 + #13#10 +
                     'Your hosts are stored in:' + #13#10 +
                     ExpandConstant('{userappdata}\PingMonitor\hosts.json') + #13#10 + #13#10 +
                     'Click Yes to keep your data (recommended)' + #13#10 +
                     'Click No to delete all data', 
                     mbConfirmation, MB_YESNO);
  
  if Response = IDNO then
  begin
    // User chose to delete data
    if DirExists(ExpandConstant('{userappdata}\PingMonitor')) then
      DelTree(ExpandConstant('{userappdata}\PingMonitor'), True, True, True);
  end;
  
  Result := True;
end;
