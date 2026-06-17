#!/usr/bin/env bash
# Build PDF ikkcu for macOS → .app + .dmg
set -euo pipefail
cd "$(dirname "$0")/.."

APP_NAME="PDF ikkcu"
DMG_NAME="PDF_ikkcu_mac.dmg"
mkdir -p .build-cache/pip .build-cache/pyinstaller
export PIP_CACHE_DIR="$PWD/.build-cache/pip"
export PYINSTALLER_CONFIG_DIR="$PWD/.build-cache/pyinstaller"

echo "[1/4] Installing dependencies..."
pip3 install -r build/requirements.txt

echo "[2/4] Building .app bundle..."
pyinstaller \
  --onefile \
  --windowed \
  --name "$APP_NAME" \
  --hidden-import pypdf \
  --hidden-import fitz \
  --hidden-import PIL \
  --hidden-import PIL.Image \
  --hidden-import PIL.ImageTk \
  pdf_ikkcu.py

echo "[3/4] Creating DMG..."
# Create a temporary folder for DMG content
mkdir -p dist/dmg_stage
cp -r "dist/${APP_NAME}.app" dist/dmg_stage/
ln -sf /Applications dist/dmg_stage/Applications

hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder dist/dmg_stage \
  -ov \
  -format UDZO \
  "$DMG_NAME"

rm -rf dist/dmg_stage

echo "[4/4] Done."
echo "Output: $DMG_NAME"
