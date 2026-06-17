#!/usr/bin/env bash
# Build PDF ikkcu for macOS → per-architecture .app + .dmg
set -euo pipefail
cd "$(dirname "$0")/.."

APP_NAME="PDF ikkcu"
mkdir -p .build-cache/pip .build-cache/pyinstaller
export PIP_CACHE_DIR="$PWD/.build-cache/pip"
export PYINSTALLER_CONFIG_DIR="$PWD/.build-cache/pyinstaller"

build_arch() {
  local arch_name="$1"
  local arch_flag="$2"
  local venv=".build-cache/venv-macos-${arch_name}"
  local dist_dir="dist/macos-${arch_name}"
  local work_dir="build/macos-${arch_name}"
  local dmg_stage=".build-cache/dmg-stage-${arch_name}"
  local dmg_name="PDF_ikkcu_mac_${arch_name}.dmg"

  echo "[${arch_name}] Creating Python environment..."
  rm -rf "$venv"
  arch "$arch_flag" python3 -m venv "$venv"

  echo "[${arch_name}] Installing dependencies..."
  arch "$arch_flag" "$venv/bin/python" -m pip install --upgrade pip
  arch "$arch_flag" "$venv/bin/python" -m pip install -r build/requirements.txt

  echo "[${arch_name}] Building .app bundle..."
  arch "$arch_flag" "$venv/bin/python" -m PyInstaller \
    --clean \
    --noconfirm \
    --windowed \
    --name "$APP_NAME" \
    --target-architecture "$arch_name" \
    --distpath "$dist_dir" \
    --workpath "$work_dir" \
    --specpath ".build-cache/specs-${arch_name}" \
    --hidden-import pypdf \
    --hidden-import fitz \
    --hidden-import pymupdf \
    --hidden-import PIL \
    --hidden-import PIL.Image \
    --hidden-import PIL.ImageTk \
    pdf_ikkcu.py

  echo "[${arch_name}] Creating DMG..."
  rm -rf "$dmg_stage"
  mkdir -p "$dmg_stage"
  cp -R "${dist_dir}/${APP_NAME}.app" "$dmg_stage/"
  ln -sf /Applications "$dmg_stage/Applications"
  hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$dmg_stage" \
    -ov \
    -format UDZO \
    "$dmg_name"
  rm -rf "$dmg_stage"
  echo "[${arch_name}] Output: $dmg_name"
}

build_arch "arm64" "-arm64"
build_arch "x86_64" "-x86_64"

echo "Done."
