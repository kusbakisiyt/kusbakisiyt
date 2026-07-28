#!/usr/bin/env bash
set -euo pipefail

# Resolves to the project root regardless of where the checkout lives.
project="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
stage="$project/build/linux/package"
output="$project/outputs/Spider-Man-Turkish-English-Deutsch-Setup_1.1.3_amd64.deb"

chmod 755 "$stage/DEBIAN/postinst" "$stage/DEBIAN/postrm"
chmod 755 "$stage/opt/spiderman/SpiderManTR"
chmod 755 "$stage/opt/spiderman/_internal/kaynaklar/duckstation/DuckStation-x64.AppImage"
chmod 755 "$stage/opt/spiderman/_internal/kaynaklar/overlay/test_kalibreli_linux"
chmod 755 "$stage/opt/spiderman/_internal/kaynaklar/provisioning/tools/linux/xdelta3"

sed -i '/^Installed-Size:/d' "$stage/DEBIAN/control"
installed_size="$(du -sk "$stage" | awk '{print $1}')"
printf 'Installed-Size: %s\n' "$installed_size" >> "$stage/DEBIAN/control"

rm -f "$output"
dpkg-deb --root-owner-group --nocheck -Zxz -z3 --build "$stage" "$output"
dpkg-deb --info "$output"
