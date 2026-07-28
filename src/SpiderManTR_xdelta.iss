; ROM/BIN and BIOS-free Windows installer
#define AppName "Spider-Man Turkish-English-Deutsch"
#define AppVersion "1.1.3"
#define AppPublisher "Kuş Bakışı"
#define AppExeName "SpiderManTR.exe"
; SourcePath is the folder containing this .iss file (src\); the project
; root is one level up. Override by editing this line if needed.
#define ProjectDir SourcePath + ".."
#define BuildDir ProjectDir + "\build\windows\launcher-dist\SpiderManTR"
#define AssetsDir ProjectDir + "\build\linux\package\opt\spiderman\_internal\kaynaklar"

[Setup]
AppId={{7F1799E5-5945-4F96-8F96-87E8266E740E}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
UninstallDisplayName={#AppName}
DefaultDirName={commonpf32}\Spiderman
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir={#ProjectDir}\outputs
OutputBaseFilename=Spider-Man-Turkish-English-Deutsch Setup
SetupIconFile={#ProjectDir}\assets\spiderman_ico.ico
Compression=lzma2/fast
SolidCompression=yes
DiskSpanning=yes
DiskSliceSize=2000000000
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#AppExeName}
LanguageDetectionMethod=uilanguage
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"; InfoBeforeFile: "{#ProjectDir}\docs\INSTALLATION_TR.txt"
Name: "english"; MessagesFile: "compiler:Default.isl"; InfoBeforeFile: "{#ProjectDir}\docs\INSTALLATION_EN.txt"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"; InfoBeforeFile: "{#ProjectDir}\docs\INSTALLATION_DE.txt"

[Messages]
turkish.SelectLanguageTitle=Dil seçin / Choose your language / Sprache wählen
turkish.SelectLanguageLabel=Dil seçin / Choose your language / Sprache wählen:
english.SelectLanguageTitle=Dil seçin / Choose your language / Sprache wählen
english.SelectLanguageLabel=Dil seçin / Choose your language / Sprache wählen:
german.SelectLanguageTitle=Dil seçin / Choose your language / Sprache wählen
german.SelectLanguageLabel=Dil seçin / Choose your language / Sprache wählen:
turkish.UninstalledMost=%1 kaldırıldı.
english.UninstalledMost=%1 was removed.
german.UninstalledMost=%1 wurde entfernt.

[CustomMessages]
turkish.desktopicon=Masaüstü simgesi oluştur
turkish.additionaloptions=Ek seçenekler:
english.desktopicon=Create a desktop shortcut
english.additionaloptions=Additional options:
german.desktopicon=Desktop-Verknüpfung erstellen
german.additionaloptions=Zusätzliche Optionen:

[Tasks]
Name: "desktopicon"; Description: "{cm:desktopicon}"; GroupDescription: "{cm:additionaloptions}"

[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#AssetsDir}\*"; DestDir: "{app}\_internal\kaynaklar"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\_internal\kaynaklar"; Permissions: users-modify
Name: "{app}\_internal\kaynaklar\oyun"; Permissions: users-modify
Name: "{app}\_internal\kaynaklar\duckstation\bios"; Permissions: users-modify

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Spider-Man"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Flags: nowait skipifsilent runasoriginaluser

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
