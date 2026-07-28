# Building from Source

The repository contains the original project code but intentionally excludes copyrighted game content and third-party binaries.

## Python

Python 3.12 is recommended.

```bash
python -m venv .venv
```

Install the pinned development dependencies:

```bash
python -m pip install -r requirements-build.txt
```

## Required external layout

Before creating a complete installer, supply files you are legally allowed to use in the documented placeholder directories:

```text
assets/
├── spiderman.png
└── spiderman_ico.ico

kaynaklar/
├── duckstation/
│   ├── duckstation-qt-x64.exe       # Windows staging
│   ├── DuckStation-x64.AppImage     # Linux staging
│   └── bios/                         # must remain empty in a distributed package
├── overlay/                          # scene data/subtitle data maintained separately
└── oyun/                             # must remain empty in a distributed package

patches/
├── spiderman_tr_from_redump.xdelta
├── spiderman_en_from_redump.xdelta
└── spiderman_de_from_redump.xdelta

tools/
├── windows/xdelta3-3.0.11-x86_64.exe
├── linux/xdelta3
└── InnoSetup6/ISCC.exe
```

The branding files are intentionally excluded from the MIT source archive. Supply only artwork you have permission to use.

## Windows

Run from PowerShell at the repository root:

```powershell
.\srcuild_windows.ps1
```

Optional parameters:

```powershell
.\srcuild_windows.ps1 -SkipInstaller
.\srcuild_windows.ps1 -ReuseBinaries
.\srcuild_windows.ps1 -SourceAssets "D:\path	o\kaynaklar" -IconPath "D:\path	o\icon.ico"
```

The script stages runtime files while rejecting game BIN files and files inside the BIOS directory.

## Linux / Debian

```bash
chmod +x src/*.sh src/packaging/linux/postinst src/packaging/linux/postrm
./src/build_linux_deb.sh /path/to/kaynaklar
```

Use `BRANDING_DIR=/path/to/assets` to provide a separately licensed PNG icon.

## Source-only checks

These checks do not require game, BIOS, emulator or patch files:

```bash
python -m compileall -q src
bash -n src/build_linux_deb.sh
bash -n src/finish_linux_deb.sh
bash -n src/rebuild_linux_launcher.sh
python -c "import xml.etree.ElementTree as ET; ET.parse('src/packaging/linux/spiderman.metainfo.xml')"
```

The GitHub Actions workflow runs equivalent checks automatically.
