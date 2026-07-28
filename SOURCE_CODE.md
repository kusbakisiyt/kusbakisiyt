# Spider-Man (2000) TR / EN / DE Localization — Source Code

Source release for the launcher, verified game-file provisioning, and real-time subtitle overlay used by the free **Spider-Man (2000) Turkish / English / German localization project**.

> **Version:** 1.1.3  
> **Maintainer:** [Kuş Bakışı](https://github.com/kusbakisiyt)  
> **Project page:** [spider-man-2000-tr-en-de-localization](https://github.com/kusbakisiyt/spider-man-2000-tr-en-de-localization)

## What is included

- A multilingual Windows/Linux launcher written in Python.
- Verified source-BIN selection and xdelta-based output preparation.
- SHA-1/SHA-256 and file-size checks that prevent incompatible disc images from being patched.
- A real-time scene-recognition subtitle overlay for games without native subtitle support.
- Windows, Linux and Debian packaging scripts.
- Open-source project documentation and automated source-quality checks.

## What is not included

This source archive intentionally contains **no game files, PlayStation BIOS, game artwork, dialogue databases, scene-capture templates, xdelta patch payloads, DuckStation binaries, xdelta3 binaries, or Spider-Man branding artwork**. These items are not covered by the MIT License in this repository.

The published end-user installer is distributed separately. Users must provide their own legally obtained compatible game BIN and PlayStation BIOS. Turkish and English use **SLES-02886**; German uses **SLES-02888**.

## Repository structure

```text
src/                      Original launcher, overlay and packaging source
assets/                   Placeholder for separately licensed branding
kaynaklar/                Placeholder for external runtime assets
patches/                   Placeholder for release-only xdelta patches
tools/                     Placeholder for external build tools
docs/                      Build, structure and upload documentation
licenses/                  Third-party license notices retained for xdelta3
.github/                   Issue templates, funding configuration and CI
```

See [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) and [docs/BUILDING.md](docs/BUILDING.md) for details.

## Development environment

Python 3.12 is recommended.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
```

Linux:

```bash
source .venv/bin/activate
python -m pip install -r requirements-build.txt
```

The source can be inspected and compiled without distributing copyrighted game content. A complete application build additionally requires the external runtime layout described in [docs/BUILDING.md](docs/BUILDING.md).

## License

The original software and documentation in this source release are provided under the [MIT License](LICENSE), except where a file or directory contains a separate notice.

The MIT License does **not** grant rights to the Spider-Man name, characters, logos, game content, PlayStation BIOS, DuckStation, xdelta3, or any other third-party material. Read [NOTICE.md](NOTICE.md) before redistributing a build.

## Türkçe

Bu arşiv, projenin bana ait Python kaynak kodunu ve derleme betiklerini içerir. Oyun BIN/ISO dosyası, BIOS, DuckStation binary'si, xdelta3 binary'si, oyun görselleri, sahne şablonları ve altyazı veritabanları bu kaynak arşivinde bulunmaz.

Kod MIT lisansıyla yayımlanmıştır. Spider-Man ve diğer üçüncü taraf unsurları MIT lisansının kapsamında değildir. Ayrıntılar için [NOTICE.md](NOTICE.md) dosyasına bakın.

## Support

The project remains free. Optional support is available through [GitHub Sponsors](https://github.com/sponsors/kusbakisiyt).
