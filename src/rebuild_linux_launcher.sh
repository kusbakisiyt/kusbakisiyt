#!/usr/bin/env bash
set -euo pipefail

# Resolves to the project root regardless of where the checkout lives.
project="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p \
  "$project/build/linux-new/launcher-dist" \
  "$project/build/linux-new/launcher-work" \
  "$project/build/linux-new/launcher-spec"

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --windowed \
  --name SpiderManTR \
  --collect-all customtkinter \
  --collect-all PIL \
  --distpath "$project/build/linux-new/launcher-dist" \
  --workpath "$project/build/linux-new/launcher-work" \
  --specpath "$project/build/linux-new/launcher-spec" \
  "$project/src/launcher.pyw"
