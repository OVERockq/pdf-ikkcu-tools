#!/usr/bin/env bash
# Build PDF.ikkcu Tools for macOS → per-architecture .app + universal .dmg
set -euo pipefail
cd "$(dirname "$0")/.."

APP_NAME="PDF.ikkcu Tools"
DMG_BASE="PDF.ikkcu_Tools_mac"
ICON="$PWD/build/icon_pdf-ikkcu.icns"
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
  local dmg_name="${DMG_BASE}_${arch_name}.dmg"

  echo "[${arch_name}] Creating Python environment..."
  rm -rf "$venv"
  arch "$arch_flag" python3 -m venv "$venv"

  echo "[${arch_name}] Installing dependencies..."
  arch "$arch_flag" "$venv/bin/python" -m pip install --upgrade pip
  arch "$arch_flag" env \
    _PYTHON_HOST_PLATFORM="macosx-11.0-${arch_name}" \
    ARCHFLAGS="-arch ${arch_name}" \
    "$venv/bin/python" -m pip install --no-cache-dir -r build/requirements.txt

  echo "[${arch_name}] Building .app bundle..."
  arch "$arch_flag" "$venv/bin/python" -m PyInstaller \
    --clean \
    --noconfirm \
    --windowed \
    --name "$APP_NAME" \
    --icon "$ICON" \
    --osx-bundle-identifier "com.ikkcu.pdf-tools" \
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
    --hidden-import tkinterdnd2 \
    --collect-all tkinterdnd2 \
    --add-data "$PWD/icon_pdf-ikkcu.png:." \
    pdf_ikkcu.py

  echo "[${arch_name}] Patching Info.plist for file associations..."
  python3 - <<PYEOF
import plistlib, pathlib
p = pathlib.Path("${dist_dir}/${APP_NAME}.app/Contents/Info.plist")
pl = plistlib.loads(p.read_bytes())
pl["CFBundleDocumentTypes"] = [
    {
        "CFBundleTypeExtensions": ["pdf", "ai"],
        "CFBundleTypeName": "PDF Document",
        "CFBundleTypeRole": "Viewer",
        "LSHandlerRank": "Alternate",
        "LSItemContentTypes": ["com.adobe.pdf"],
        "CFBundleTypeIconFile": "icon_pdf-ikkcu.png",
    }
]
pl["UTImportedTypeDeclarations"] = [
    {
        "UTTypeConformsTo": ["public.data", "public.composite-content"],
        "UTTypeDescription": "Portable Document Format",
        "UTTypeIdentifier": "com.adobe.pdf",
        "UTTypeTagSpecification": {
            "public.filename-extension": ["pdf"],
            "public.mime-type": "application/pdf",
        },
    }
]
p.write_bytes(plistlib.dumps(pl))
print("  Info.plist patched.")
PYEOF

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

# Universal DMG (ditto로 arm64+x86_64 합본)
echo "[universal] Creating universal .app..."
ARM_APP="dist/macos-arm64/${APP_NAME}.app"
X86_APP="dist/macos-x86_64/${APP_NAME}.app"
UNI_DIR="dist/macos-universal"
UNI_APP="${UNI_DIR}/${APP_NAME}.app"
rm -rf "$UNI_DIR"
mkdir -p "$UNI_DIR"
cp -R "$ARM_APP" "$UNI_APP"

# 각 아키텍처 Mach-O 파일을 lipo로 합치기
while IFS= read -r -d '' x86_bin; do
  rel="${x86_bin#${X86_APP}/}"
  arm_bin="${ARM_APP}/${rel}"
  uni_bin="${UNI_APP}/${rel}"
  if [ -f "$arm_bin" ] && file "$x86_bin" | grep -q "Mach-O"; then
    lipo -create "$arm_bin" "$x86_bin" -output "$uni_bin" 2>/dev/null || true
  fi
done < <(find "$X86_APP" -type f -print0)

echo "[universal] Creating universal DMG..."
UNI_STAGE=".build-cache/dmg-stage-universal"
rm -rf "$UNI_STAGE"
mkdir -p "$UNI_STAGE"
cp -R "$UNI_APP" "$UNI_STAGE/"
ln -sf /Applications "$UNI_STAGE/Applications"
hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$UNI_STAGE" \
  -ov \
  -format UDZO \
  "${DMG_BASE}_universal.dmg"
rm -rf "$UNI_STAGE"
echo "[universal] Output: ${DMG_BASE}_universal.dmg"

echo "Done. Outputs:"
ls -lh "${DMG_BASE}"_*.dmg
