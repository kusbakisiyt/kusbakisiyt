"""ROM/BIN and BIOS provisioning for the Spider-Man launcher.

The distributed package contains only delta patches.  A source BIN is never
modified: xdelta writes to a temporary file in the game directory, the output
is verified, and only then is it moved into its final location.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable


APP_TITLE = "Spider-Man Turkish-English-Deutsch"

LANGUAGE_NAMES = {
    "tr": "Türkçe",
    "en": "English",
    "de": "Deutsch",
}

# Each source entry is tied to its own delta.  This prevents a similarly named
# but byte-incompatible disc image from being patched accidentally.
GAME_PROFILES = {
    "tr": {
        "serial": "SLES-02886",
        "output_name": "spiderman_tr.bin",
        "target_size": 730_056_096,
        "target_sha256": "9ab2b3f8f651b84bbfe1bbd81a72bb610b7f925ef86243b3baa2df686742157b",
        "sources": [
            {
                "size": 730_056_096,
                "sha256": "63f4ab72bb64acb88869d17dbfd511384e16ca136a91b92adf9f225cd9c38eb8",
                "patch": "spiderman_tr_from_redump.xdelta",
            }
        ],
    },
    "en": {
        "serial": "SLES-02886",
        "output_name": "spiderman_en.bin",
        "target_size": 730_056_096,
        "target_sha256": "d335f63096b6d0e3467bbd4f7e9144efa5820686c6d0f9567a1ec4e606eed025",
        "sources": [
            {
                "size": 730_056_096,
                "sha256": "63f4ab72bb64acb88869d17dbfd511384e16ca136a91b92adf9f225cd9c38eb8",
                "patch": "spiderman_en_from_redump.xdelta",
            }
        ],
    },
    "de": {
        "serial": "SLES-02888",
        "output_name": "spiderman_de.bin",
        "target_size": 718_507_776,
        "target_sha256": "926b64804123fd50f8aa120a208c2b0f9262c4698b5c5def4a9d3a4a6b79d20e",
        "sources": [
            {
                "size": 718_507_776,
                "sha1": "14c60da1f82b84c5674d46c26f343f0aa7f3060c",
                "patch": "spiderman_de_from_redump.xdelta",
            }
        ],
    },
}


TEXT = {
    "choose_bios": (
        "PlayStation BIOS dosyanızı seçin (512 KB).\n\n"
        "Select your PlayStation BIOS file (512 KB).\n\n"
        "Wählen Sie Ihre PlayStation-BIOS-Datei (512 KB)."
    ),
    "bad_bios": (
        "Seçilen dosya desteklenen 512 KB PlayStation BIOS dosyası değil.\n\n"
        "The selected file is not a supported 512 KB PlayStation BIOS.\n\n"
        "Die ausgewählte Datei ist kein unterstütztes 512-KB-PlayStation-BIOS."
    ),
    "choose_bin": (
        "{language} için değiştirilmemiş {serial} BIN dosyasını seçin.\n\n"
        "Select the unmodified {serial} BIN for {language}.\n\n"
        "Wählen Sie die unveränderte {serial}-BIN-Datei für {language}."
    ),
    "checking": (
        "Dosya doğrulanıyor… / Verifying file… / Datei wird überprüft…"
    ),
    "wrong_bin": (
        "Bu BIN seçilen sürümle birebir uyumlu değil; hiçbir dosya değiştirilmedi.\n"
        "Gerekli sürüm: {serial} ({language})\n\n"
        "This BIN is not byte-compatible with the selected edition; no file was changed.\n"
        "Required edition: {serial} ({language})\n\n"
        "Diese BIN-Datei ist nicht bytegenau kompatibel; keine Datei wurde verändert.\n"
        "Benötigte Version: {serial} ({language})"
    ),
    "preparing": (
        "{language} hazırlanıyor… / Preparing {language}… / "
        "{language} wird vorbereitet…"
    ),
    "no_space": (
        "Çıktıyı güvenle oluşturmak için yeterli boş alan yok.\n\n"
        "There is not enough free space to create the output safely.\n\n"
        "Zum sicheren Erstellen der Ausgabedatei ist nicht genügend Speicherplatz vorhanden."
    ),
    "missing_component": (
        "Gerekli kurulum bileşeni bulunamadı; paket eksik veya hasarlı.\n\n"
        "A required setup component is missing; the package is incomplete or damaged.\n\n"
        "Eine benötigte Installationskomponente fehlt; das Paket ist unvollständig oder beschädigt."
    ),
    "failed": (
        "Oyun dosyası hazırlanamadı; kaynak dosyanız değiştirilmedi.\n\n"
        "The game file could not be prepared; your source file was not changed.\n\n"
        "Die Spieldatei konnte nicht vorbereitet werden; Ihre Quelldatei wurde nicht verändert."
    ),
    "verify_failed": (
        "Oluşturulan dosya doğrulamadan geçemedi ve silindi.\n\n"
        "The generated file failed verification and was removed.\n\n"
        "Die erzeugte Datei hat die Prüfung nicht bestanden und wurde gelöscht."
    ),
    "ready": (
        "{language} başarıyla hazırlandı.\n\n"
        "{language} was prepared successfully.\n\n"
        "{language} wurde erfolgreich vorbereitet."
    ),
    "add_another": (
        "Başka bir oyun dili eklemek ister misiniz?\n\n"
        "Would you like to add another game language?\n\n"
        "Möchten Sie eine weitere Spielsprache hinzufügen?"
    ),
}

LANGUAGE_NAMES_LOCALIZED = {
    "tr": {"tr": "Türkçe", "en": "Turkish", "de": "Türkisch"},
    "en": {"tr": "İngilizce", "en": "English", "de": "Englisch"},
    "de": {"tr": "Almanca", "en": "German", "de": "Deutsch"},
}

CHOOSE_BIN_TEXT = (
    "{tr_name} için değiştirilmemiş {serial} BIN dosyasını seçin.\n\n"
    "Select the unmodified {serial} BIN for {en_name}.\n\n"
    "Wählen Sie die unveränderte {serial}-BIN-Datei für {de_name}."
)

WRONG_BIN_TEXT = (
    "Bu BIN {tr_name} sürümüyle birebir uyumlu değil; hiçbir dosya değiştirilmedi.\n\n"
    "This BIN is not byte-compatible with the {en_name} edition; no file was changed.\n\n"
    "Diese BIN-Datei ist nicht bytegenau mit der {de_name}-Version kompatibel; "
    "keine Datei wurde verändert."
)


def _sha256(path: Path, progress: Callable[[str], None] | None = None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(8 * 1024 * 1024)
            if not block:
                break
            digest.update(block)
    if progress:
        progress(TEXT["checking"])
    return digest.hexdigest()


def _sha1(path: Path, progress: Callable[[str], None] | None = None) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as stream:
        while True:
            block = stream.read(8 * 1024 * 1024)
            if not block:
                break
            digest.update(block)
    if progress:
        progress(TEXT["checking"])
    return digest.hexdigest()


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def find_bios(bios_directory: Path) -> Path | None:
    if not bios_directory.exists():
        return None
    for candidate in bios_directory.iterdir():
        if candidate.is_file() and candidate.stat().st_size == 512 * 1024:
            return candidate
    return None


def ensure_bios(parent, bios_directory: Path) -> bool:
    if find_bios(bios_directory):
        return True

    messagebox.showinfo(APP_TITLE, TEXT["choose_bios"], parent=parent)
    selected = filedialog.askopenfilename(
        parent=parent,
        title=APP_TITLE,
        filetypes=[
            ("PlayStation BIOS", "*.bin *.BIN *.rom *.ROM"),
            ("All files", "*.*"),
        ],
    )
    if not selected:
        return False

    source = Path(selected)
    try:
        if not source.is_file() or source.stat().st_size != 512 * 1024:
            messagebox.showerror(APP_TITLE, TEXT["bad_bios"], parent=parent)
            return False
        _atomic_copy(source, bios_directory / source.name)
    except OSError:
        messagebox.showerror(APP_TITLE, TEXT["failed"], parent=parent)
        return False
    return True


def game_output_path(game_directory: Path, language: str) -> Path:
    return game_directory / GAME_PROFILES[language]["output_name"]


def game_is_ready(game_directory: Path, language: str, verify: bool = True) -> bool:
    profile = GAME_PROFILES[language]
    output = game_output_path(game_directory, language)
    try:
        if not output.is_file() or output.stat().st_size != profile["target_size"]:
            return False
        if verify:
            return _sha256(output) == profile["target_sha256"]
        return True
    except OSError:
        return False


def select_source(parent, language: str, progress=None) -> tuple[Path, dict] | None:
    profile = GAME_PROFILES[language]
    language_name = LANGUAGE_NAMES[language]
    localized_names = LANGUAGE_NAMES_LOCALIZED[language]
    prompt = CHOOSE_BIN_TEXT.format(
        serial=profile["serial"],
        tr_name=localized_names["tr"],
        en_name=localized_names["en"],
        de_name=localized_names["de"],
    )
    messagebox.showinfo(APP_TITLE, prompt, parent=parent)
    selected = filedialog.askopenfilename(
        parent=parent,
        title=f"{language_name} — {profile['serial']}",
        filetypes=[
            ("PlayStation BIN", "*.bin *.BIN"),
            ("All files", "*.*"),
        ],
    )
    if not selected:
        return None

    source = Path(selected)
    try:
        source_size = source.stat().st_size
    except OSError:
        source_size = -1

    matching_by_size = [
        item for item in profile["sources"] if item["size"] == source_size
    ]
    if matching_by_size:
        sha256_items = [item for item in matching_by_size if "sha256" in item]
        if sha256_items:
            source_hash = _sha256(source, progress)
            for item in sha256_items:
                if source_hash.lower() == item["sha256"].lower():
                    return source, item
        sha1_items = [item for item in matching_by_size if "sha1" in item]
        if sha1_items:
            source_hash = _sha1(source, progress)
            for item in sha1_items:
                if source_hash.lower() == item["sha1"].lower():
                    return source, item

    messagebox.showerror(
        APP_TITLE,
        WRONG_BIN_TEXT.format(
            tr_name=localized_names["tr"],
            en_name=localized_names["en"],
            de_name=localized_names["de"],
        ),
        parent=parent,
    )
    return None


def _xdelta_binary(provision_directory: Path) -> Path:
    if sys.platform.startswith("win"):
        return provision_directory / "tools" / "windows" / "xdelta3.exe"
    return provision_directory / "tools" / "linux" / "xdelta3"


def prepare_game(
    language: str,
    source: Path,
    source_profile: dict,
    game_directory: Path,
    provision_directory: Path,
    child_environment: dict | None = None,
    progress: Callable[[str], None] | None = None,
) -> tuple[bool, str]:
    profile = GAME_PROFILES[language]
    language_name = LANGUAGE_NAMES[language]
    output = game_output_path(game_directory, language)
    patch = provision_directory / "patches" / source_profile["patch"]
    xdelta = _xdelta_binary(provision_directory)

    if not patch.is_file() or not xdelta.is_file():
        return False, TEXT["missing_component"]

    try:
        free_bytes = shutil.disk_usage(game_directory).free
    except OSError:
        free_bytes = 0
    if free_bytes < profile["target_size"] + 128 * 1024 * 1024:
        return False, TEXT["no_space"]

    if progress:
        progress(TEXT["preparing"].format(language=language_name))

    game_directory.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{profile['output_name']}.", suffix=".building", dir=game_directory
    )
    os.close(fd)
    temporary = Path(temporary_name)
    temporary.unlink(missing_ok=True)

    command = [
        str(xdelta),
        "-d",
        "-f",
        "-s",
        str(source),
        str(patch),
        str(temporary),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=str(provision_directory),
            env=child_environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=(
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                if sys.platform.startswith("win")
                else 0
            ),
            check=False,
        )
        if completed.returncode != 0 or not temporary.is_file():
            return False, TEXT["failed"]
        if temporary.stat().st_size != profile["target_size"]:
            return False, TEXT["verify_failed"]
        if _sha256(temporary, progress) != profile["target_sha256"]:
            return False, TEXT["verify_failed"]

        os.replace(temporary, output)
        cue = output.with_suffix(".cue")
        cue.write_text(
            f'FILE "{output.name}" BINARY\n'
            "  TRACK 01 MODE2/2352\n"
            "    INDEX 01 00:00:00\n",
            encoding="utf-8",
            newline="\n",
        )
        marker = game_directory / ".prepared_games.json"
        state = {}
        if marker.exists():
            try:
                state = json.loads(marker.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                state = {}
        state[language] = {
            "serial": profile["serial"],
            "sha256": profile["target_sha256"],
            "size": profile["target_size"],
        }
        marker.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True, TEXT["ready"].format(language=language_name)
    except OSError:
        return False, TEXT["failed"]
    finally:
        temporary.unlink(missing_ok=True)


def ask_add_another(parent) -> bool:
    return messagebox.askyesno(
        APP_TITLE,
        TEXT["add_another"],
        parent=parent,
    )
