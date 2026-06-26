#!/usr/bin/env bash
# Build PDF.ikkcu Tools for Linux (Debian/Ubuntu amd64) → binary + .deb
# Docker가 필요합니다.
set -euo pipefail
cd "$(dirname "$0")/.."

PKG_NAME="pdf-ikkcu-tools"
APP_NAME="PDF.ikkcu Tools"
VERSION="2.0.0"
ARCH="amd64"
DEB_OUT="${PKG_NAME}_${VERSION}_${ARCH}.deb"

echo "[linux] Building + packaging via Docker (Ubuntu 22.04 / amd64)..."
docker run --rm \
  --platform linux/amd64 \
  -v "$PWD":/work \
  ubuntu:22.04 \
  bash -c "
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y --no-install-recommends \
      python3 python3-pip python3-venv python3-tk \
      libpython3.10 libpython3.10-dev \
      libgl1 libglib2.0-0 libsm6 libxrender1 libxext6 \
      binutils dpkg-dev file > /dev/null 2>&1

    pip3 install --quiet -r /work/build/requirements.txt

    cd /tmp
    cp /work/pdf_ikkcu.py .

    pyinstaller \
      --onefile \
      --name pdf_ikkcu_tools \
      --hidden-import pypdf \
      --hidden-import fitz \
      --hidden-import pymupdf \
      --hidden-import PIL \
      --hidden-import PIL.Image \
      --hidden-import PIL.ImageTk \
      pdf_ikkcu.py

    PKG_DIR=\"/tmp/pkg/${PKG_NAME}_${VERSION}_${ARCH}\"
    rm -rf \"\$PKG_DIR\"
    install -d -m 755 \"\${PKG_DIR}/usr/local/bin\"
    install -d -m 755 \"\${PKG_DIR}/usr/share/applications\"
    install -d -m 755 \"\${PKG_DIR}/usr/share/doc/${PKG_NAME}\"
    install -d -m 755 \"\${PKG_DIR}/DEBIAN\"

    install -m 755 /tmp/dist/pdf_ikkcu_tools \"\${PKG_DIR}/usr/local/bin/\"

    cat > \"\${PKG_DIR}/usr/share/applications/pdf-ikkcu-tools.desktop\" <<'DESKTOP'
[Desktop Entry]
Name=${APP_NAME}
GenericName=PDF Tool
Comment=Free PDF encryption, editing, merging, splitting, compression
Exec=pdf_ikkcu_tools
Terminal=false
Type=Application
Categories=Office;Utility;
Keywords=PDF;encrypt;merge;split;compress;
DESKTOP

    cat > \"\${PKG_DIR}/usr/share/doc/${PKG_NAME}/copyright\" <<'CR'
${APP_NAME} -- Freeware PDF Tool
Copyright 2025 ikkcu.com
This software is provided as freeware. Free to use, no warranty.
CR

    INSTALLED_SIZE=\$(du -sk \"\${PKG_DIR}/usr\" | cut -f1)
    cat > \"\${PKG_DIR}/DEBIAN/control\" <<CTRL
Package: ${PKG_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Installed-Size: \${INSTALLED_SIZE}
Depends: libgl1, python3-tk
Maintainer: ikkcu <noreply@ikkcu.com>
Description: ${APP_NAME} -- Freeware PDF Tool
 Free GUI tool for PDF encryption, page editing with preview,
 merging, splitting, and compression.
CTRL

    dpkg-deb --build --root-owner-group \"\$PKG_DIR\" \"/tmp/${DEB_OUT}\"
    cp \"/tmp/${DEB_OUT}\" /work/
    echo '[linux] .deb built successfully.'
  "

echo "[linux] Output: $DEB_OUT"
ls -lh "$DEB_OUT"
