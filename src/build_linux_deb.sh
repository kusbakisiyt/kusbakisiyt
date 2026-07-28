#!/usr/bin/env bash
set -euo pipefail

CODE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$CODE_DIR/.." && pwd)"
# Pass the asset folder as the first argument, or drop a "kaynaklar" folder
# next to the project root and the default below will pick it up.
ASSET_DIR="${1:-$PROJECT_DIR/kaynaklar}"
BRANDING_DIR="${BRANDING_DIR:-$PROJECT_DIR/assets}"
BUILD_ROOT="${BUILD_ROOT:-$PROJECT_DIR/build/linux}"
VENV_DIR="$BUILD_ROOT/venv"
WORK_DIR="$BUILD_ROOT/work"
OUTPUT_DIR="${OUTPUT_DIR:-$PROJECT_DIR/outputs}"
PACKAGE_NAME="Spider-Man-Turkish-English-Deutsch-Setup_1.1.3_amd64.deb"
SKIP_PACKAGE="${SKIP_PACKAGE:-0}"

export PIP_CACHE_DIR="$BUILD_ROOT/pip-cache"
export PYINSTALLER_CONFIG_DIR="$BUILD_ROOT/pyinstaller-config"
export TMPDIR="$BUILD_ROOT/tmp"

for required in \
    "$CODE_DIR/launcher.pyw" \
    "$CODE_DIR/game_setup.py" \
    "$CODE_DIR/test_kalibreli_linux.py" \
    "$ASSET_DIR/duckstation/DuckStation-x64.AppImage" \
    "$PROJECT_DIR/tools/linux/xdelta3" \
    "$BRANDING_DIR/spiderman.png"; do
    if [[ ! -f "$required" ]]; then
        echo "Hata: zorunlu dosya bulunamadi: $required" >&2
        exit 1
    fi
done

if [[ "$SKIP_PACKAGE" != "1" ]]; then
    for required_patch in \
        spiderman_tr_from_redump.xdelta \
        spiderman_en_from_redump.xdelta \
        spiderman_de_from_redump.xdelta; do
        if [[ ! -f "$PROJECT_DIR/patches/$required_patch" ]]; then
            echo "Hata: zorunlu yama bulunamadi: $required_patch" >&2
            exit 1
        fi
    done
fi

mkdir -p "$BUILD_ROOT" "$OUTPUT_DIR" "$TMPDIR"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    python3 -m venv "$VENV_DIR"
fi
if ! "$VENV_DIR/bin/python" - <<'PY'
from importlib.metadata import version
required = {
    "pyinstaller": "6.20.0",
    "customtkinter": "6.0.0",
    "Pillow": "11.3.0",
    "opencv-python-headless": "4.13.0.92",
    "numpy": "2.4.6",
    "mss": "10.2.0",
}
raise SystemExit(any(version(name) != expected for name, expected in required.items()))
PY
then
    "$VENV_DIR/bin/python" -m pip install \
        "pyinstaller==6.20.0" \
        "customtkinter==6.0.0" \
        "Pillow==11.3.0" \
        "opencv-python-headless==4.13.0.92" \
        "numpy==2.4.6" \
        "mss==10.2.0"
fi

PYINSTALLER_BIN="$VENV_DIR/bin/pyinstaller"
ARCHIVE_VIEWER_BIN="$VENV_DIR/bin/pyi-archive_viewer"

rm -rf "$WORK_DIR"
mkdir -p \
    "$WORK_DIR/overlay-dist" \
    "$WORK_DIR/overlay-work" \
    "$WORK_DIR/launcher-dist" \
    "$WORK_DIR/launcher-work" \
    "$WORK_DIR/package/DEBIAN" \
    "$WORK_DIR/package/usr/share/applications" \
    "$WORK_DIR/package/usr/share/metainfo" \
    "$WORK_DIR/package/usr/share/icons/hicolor/256x256/apps"

"$PYINSTALLER_BIN" --noconfirm --clean --onefile --windowed \
    --name test_kalibreli_linux \
    --collect-all cv2 --collect-all numpy --collect-all mss \
    --distpath "$WORK_DIR/overlay-dist" \
    --workpath "$WORK_DIR/overlay-work" \
    --specpath "$WORK_DIR/overlay-spec" \
    "$CODE_DIR/test_kalibreli_linux.py"

"$ARCHIVE_VIEWER_BIN" -l \
    "$WORK_DIR/overlay-dist/test_kalibreli_linux" \
    > "$WORK_DIR/overlay-archive-contents.txt"
grep -q "cv2" "$WORK_DIR/overlay-archive-contents.txt"

"$PYINSTALLER_BIN" --noconfirm --clean --onedir --windowed \
    --name SpiderManTR \
    --collect-all customtkinter --collect-all PIL \
    --distpath "$WORK_DIR/launcher-dist" \
    --workpath "$WORK_DIR/launcher-work" \
    --specpath "$WORK_DIR/launcher-spec" \
    "$CODE_DIR/launcher.pyw"

package_app="$WORK_DIR/package/opt/spiderman"
package_assets="$package_app/_internal/kaynaklar"
mkdir -p "$package_assets"
cp -a "$WORK_DIR/launcher-dist/SpiderManTR/." "$package_app/"

rsync -a --delete \
    --exclude='.hazirlikTamam' \
    --exclude='.kurulumtamam' \
    --exclude='launcher_config.json' \
    --exclude='*.bin' \
    --exclude='*.BIN' \
    --exclude='build/***' \
    --exclude='dist/***' \
    --exclude='/duckstation/bios/***' \
    "$ASSET_DIR/" "$package_assets/"

mkdir -p \
    "$package_assets/oyun" \
    "$package_assets/duckstation/bios" \
    "$package_assets/provisioning/patches" \
    "$package_assets/provisioning/tools/linux" \
    "$package_assets/provisioning/licenses"

cp -a "$PROJECT_DIR/patches/." "$package_assets/provisioning/patches/"
install -m 755 "$PROJECT_DIR/tools/linux/xdelta3" \
    "$package_assets/provisioning/tools/linux/xdelta3"
cp -a "$PROJECT_DIR/licenses/." "$package_assets/provisioning/licenses/"

install -m 644 "$CODE_DIR/test_kalibreli.py" \
    "$package_assets/overlay/test_kalibreli.py"
install -m 644 "$CODE_DIR/test_kalibreli_linux.py" \
    "$package_assets/overlay/test_kalibreli_linux.py"
install -m 755 "$WORK_DIR/overlay-dist/test_kalibreli_linux" \
    "$package_assets/overlay/test_kalibreli_linux"

for required_overlay_file in \
    test_kalibreli.py \
    test_kalibreli_linux.py \
    test_kalibreli_linux; do
    if [[ ! -s "$package_assets/overlay/$required_overlay_file" ]]; then
        echo "Hata: zorunlu overlay dosyasi eksik: $required_overlay_file" >&2
        exit 1
    fi
done

if find "$package_assets/oyun" -maxdepth 1 -type f -iname '*.bin' -print -quit |
    grep -q .; then
    echo "Hata: Linux paket sahnesinde oyun BIN dosyasi bulundu." >&2
    exit 1
fi
if find "$package_assets/duckstation/bios" -type f -print -quit | grep -q .; then
    echo "Hata: Linux paket sahnesinde BIOS dosyasi bulundu." >&2
    exit 1
fi

install -m 644 "$CODE_DIR/packaging/linux/control" \
    "$WORK_DIR/package/DEBIAN/control"
install -m 755 "$CODE_DIR/packaging/linux/postinst" \
    "$WORK_DIR/package/DEBIAN/postinst"
install -m 755 "$CODE_DIR/packaging/linux/postrm" \
    "$WORK_DIR/package/DEBIAN/postrm"
install -m 644 "$CODE_DIR/packaging/linux/spiderman.desktop" \
    "$WORK_DIR/package/usr/share/applications/spiderman.desktop"
install -m 644 "$CODE_DIR/packaging/linux/spiderman.metainfo.xml" \
    "$WORK_DIR/package/usr/share/metainfo/spiderman.metainfo.xml"
install -m 644 "$BRANDING_DIR/spiderman.png" \
    "$WORK_DIR/package/usr/share/icons/hicolor/256x256/apps/spiderman.png"

find "$package_app" -type d -exec chmod 755 {} +
find "$package_app" -type f -exec chmod 644 {} +
chmod 755 "$package_app/SpiderManTR"
chmod 755 "$package_assets/duckstation/DuckStation-x64.AppImage"
chmod 755 "$package_assets/overlay/test_kalibreli_linux"
chmod 755 "$package_assets/provisioning/tools/linux/xdelta3"

# The launcher creates selected-language BINs, BIOS, saves, settings and
# subtitle runtime data in these directories.
chmod 777 "$package_assets"
find "$package_assets/duckstation" -type d -exec chmod 777 {} +
find "$package_assets/duckstation" -type f -exec chmod 666 {} +
chmod 755 "$package_assets/duckstation/DuckStation-x64.AppImage"
find "$package_assets/overlay" -type d -exec chmod 777 {} +
find "$package_assets/overlay" -type f -exec chmod 666 {} +
chmod 755 "$package_assets/overlay/test_kalibreli_linux"
find "$package_assets/oyun" -type d -exec chmod 777 {} +
find "$package_assets/oyun" -type f -exec chmod 666 {} +
chmod 777 "$package_assets/duckstation/bios"

installed_size=$(du -sk "$WORK_DIR/package" | awk '{print $1}')
printf 'Installed-Size: %s\n' "$installed_size" \
    >> "$WORK_DIR/package/DEBIAN/control"

if [[ "$SKIP_PACKAGE" == "1" ]]; then
    echo "Linux derleme sahnesi hazir; .deb olusturma atlandi."
    exit 0
fi

# The stage lives on Windows/DrvFS, which reports its control directory as
# mode 0777 even after chmod.  The actual control files are explicitly staged
# above, so skip only dpkg-deb's host-mount permission check.
dpkg-deb --root-owner-group --nocheck -Zxz -z3 --build \
    "$WORK_DIR/package" "$OUTPUT_DIR/$PACKAGE_NAME"

echo "Hazir: $OUTPUT_DIR/$PACKAGE_NAME"
