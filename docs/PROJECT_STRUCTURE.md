# Project Structure

## Original source

- `src/launcher.pyw` — multilingual GUI launcher, first-run preparation and process management.
- `src/game_setup.py` — compatible source-image validation, BIOS selection, xdelta provisioning and output verification.
- `src/test_kalibreli.py` — Windows-capable scene-recognition subtitle overlay.
- `src/test_kalibreli_linux.py` — Linux packaging entry point for the subtitle overlay.

## Packaging

- `src/build_windows.ps1` — stages assets, rejects game/BIOS files, builds PyInstaller binaries and invokes Inno Setup.
- `src/build_linux_deb.sh` — builds Linux binaries and a Debian package while rejecting game/BIOS files.
- `src/SpiderManTR_xdelta.iss` — current Windows installer definition for version 1.1.3.
- `src/packaging/linux/` — Debian control, desktop integration, AppStream metadata and install/remove scripts.

## External/release-only inputs

The build scripts expect separate directories for runtime assets, delta patches, third-party tools and branding. Placeholder documentation is included in `assets/`, `kaynaklar/`, `patches/` and `tools/`. Their excluded contents are not MIT-licensed by this repository.
