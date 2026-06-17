#!/usr/bin/env bash
# Build PDF ikkcu for Linux → binary + .deb package
set -euo pipefail
cd "$(dirname "$0")/.."

PKG_NAME="pdf-ikkcu"
VERSION="1.0.0"
ARCH="amd64"
PKG_DIR="dist/${PKG_NAME}_${VERSION}_${ARCH}"
mkdir -p .build-cache/pip .build-cache/pyinstaller
export PIP_CACHE_DIR="$PWD/.build-cache/pip"
export PYINSTALLER_CONFIG_DIR="$PWD/.build-cache/pyinstaller"

echo "[1/5] Installing dependencies..."
pip3 install -r build/requirements.txt

echo "[2/5] Building binary..."
pyinstaller \
  --onefile \
  --name pdf_ikkcu \
  --hidden-import pypdf \
  --hidden-import fitz \
  --hidden-import PIL \
  --hidden-import PIL.Image \
  --hidden-import PIL.ImageTk \
  pdf_ikkcu.py

echo "[3/5] Preparing .deb structure..."
rm -rf "$PKG_DIR"
mkdir -p "${PKG_DIR}/usr/local/bin"
mkdir -p "${PKG_DIR}/usr/share/applications"
mkdir -p "${PKG_DIR}/usr/share/doc/${PKG_NAME}"
mkdir -p "${PKG_DIR}/DEBIAN"

cp dist/pdf_ikkcu "${PKG_DIR}/usr/local/bin/"
chmod 755 "${PKG_DIR}/usr/local/bin/pdf_ikkcu"

cat > "${PKG_DIR}/usr/share/applications/pdf-ikkcu.desktop" <<'EOF'
[Desktop Entry]
Name=PDF ikkcu
GenericName=PDF Tool
Comment=Free PDF encryption, editing, merging, splitting, compression
Exec=pdf_ikkcu
Terminal=false
Type=Application
Categories=Office;Utility;
Keywords=PDF;encrypt;merge;split;compress;
EOF

cat > "${PKG_DIR}/usr/share/doc/${PKG_NAME}/copyright" <<'EOF'
PDF ikkcu — Freeware PDF Tool
Copyright 2025 PDF ikkcu contributors
This software is provided as freeware. Free to use, no warranty.
EOF

echo "[4/5] Writing DEBIAN/control..."
INSTALLED_SIZE=$(du -sk "${PKG_DIR}/usr" | cut -f1)
cat > "${PKG_DIR}/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_SIZE}
Depends: libgl1, python3-tk
Maintainer: PDF ikkcu <noreply@pdf-ikkcu.com>
Description: PDF ikkcu — Freeware PDF Tool
 Free GUI tool for PDF encryption, page editing with preview,
 merging, splitting, and compression.
EOF

echo "[5/5] Building .deb..."
dpkg-deb --build --root-owner-group "$PKG_DIR"
echo "Output: ${PKG_DIR}.deb"
