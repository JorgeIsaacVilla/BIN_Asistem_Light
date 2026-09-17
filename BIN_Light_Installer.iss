#define MyAppName "BIN IA Asistem — Light"
#define MyAppVersion "1.6.18"
#define MyAppPublisher "BIN IA Asistem"
#define MyAppExeName "BIN_Light.exe"

[Setup]
AppId={{4D265D44-7742-4FA8-90A1-B4F285A503B8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={localappdata}\Programs\BIN Light
DefaultGroupName=BIN Light

PrivilegesRequired=lowest

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

OutputDir=installer
OutputBaseFilename=BIN_Light_v1.6.18_Setup

SetupIconFile=assets\bin_face.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

Compression=lzma2
SolidCompression=yes

WizardStyle=modern

DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no


[Languages]

Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"


[Tasks]

Name: "desktopicon"; \
    Description: "Crear acceso directo en el escritorio"; \
    GroupDescription: "Accesos directos:"; \
    Flags: unchecked


[Files]

; ============================================================
; BIN IA ASISTEM — LIGHT v1.6.18
; DISTRIBUCIÓN ONEDIR GENERADA POR PYINSTALLER
; ============================================================

Source: "dist\BIN_Light\*"; \
    DestDir: "{app}"; \
    Excludes: "_internal\data\tareas.json,_internal\data\memoria.json,_internal\data\configuracion.json,_internal\data\notificaciones.json,_internal\data\comandos_teclado.json"; \
    Flags: ignoreversion recursesubdirs createallsubdirs


; ============================================================
; DATOS MODIFICABLES DE BIN
;
; onlyifdoesntexist protege los datos existentes cuando en el
; futuro se instale una actualización encima de BIN Light.
; ============================================================

Source: "dist\BIN_Light\_internal\data\tareas.json"; \
    DestDir: "{app}\_internal\data"; \
    Flags: onlyifdoesntexist

Source: "dist\BIN_Light\_internal\data\memoria.json"; \
    DestDir: "{app}\_internal\data"; \
    Flags: onlyifdoesntexist

Source: "dist\BIN_Light\_internal\data\configuracion.json"; \
    DestDir: "{app}\_internal\data"; \
    Flags: onlyifdoesntexist

Source: "dist\BIN_Light\_internal\data\notificaciones.json"; \
    DestDir: "{app}\_internal\data"; \
    Flags: onlyifdoesntexist

Source: "dist\BIN_Light\_internal\data\comandos_teclado.json"; \
    DestDir: "{app}\_internal\data"; \
    Flags: onlyifdoesntexist


[Icons]

Name: "{autoprograms}\BIN Light"; \
    Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"

Name: "{autodesktop}\BIN Light"; \
    Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"; \
    Tasks: desktopicon


[Run]

Filename: "{app}\{#MyAppExeName}"; \
    Description: "Ejecutar BIN Light"; \
    WorkingDir: "{app}"; \
    Flags: nowait postinstall skipifsilent