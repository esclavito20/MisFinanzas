#define MyAppName "Mis Finanzas"
#define MyAppPublisher "Kevin"
#define MyAppExeName "MisFinanzas.exe"

; La version se toma de VERSION.txt a traves de CREAR_INSTALADOR.bat
; (/DMyAppVersion=...). El valor por defecto mantiene compilable el script
; cuando se invoca ISCC.exe de forma directa.
#ifndef MyAppVersion
  #define MyAppVersion "3.0.0"
#endif

[Setup]
AppId={{7B4E2D55-C3C0-4D9D-9A73-5D6F5F8E0A21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Mis Finanzas
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=MisFinanzas_Setup_{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
CloseApplications=yes
CloseApplicationsFilter=MisFinanzas.exe
RestartApplications=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\assets\MisFinanzas.ico
VersionInfoVersion={#MyAppVersion}.0
VersionInfoDescription=Aplicacion de finanzas personales
VersionInfoProductName=Mis Finanzas
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "..\dist\MisFinanzas\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Mis Finanzas"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Mis Finanzas"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir Mis Finanzas"; Flags: nowait postinstall skipifsilent
