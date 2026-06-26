#!/usr/bin/env bash
# Windows EXE 빌드 (Docker + Wine)
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="pdf-ikkcu-win-builder"
OUT_DIR="dist/windows"

echo "[windows] Docker 이미지 빌드 (처음 실행 시 10~20분 소요)..."
docker build --platform linux/amd64 -f build/Dockerfile.windows -t "$IMAGE" .

mkdir -p "$OUT_DIR"

echo "[windows] PyInstaller 실행 중..."
docker run --rm \
    --platform linux/amd64 \
    -v "$PWD:/src" \
    -w /src \
    "$IMAGE" \
    bash -c "
        xvfb-run wine python -m PyInstaller \
            --clean --noconfirm \
            --onefile \
            --windowed \
            --name 'PDF.ikkcu_Tools' \
            --icon 'build/icon_pdf-ikkcu.ico' \
            --add-data 'icon_pdf-ikkcu.png;.' \
            --hidden-import pypdf \
            --hidden-import fitz \
            --hidden-import pymupdf \
            --hidden-import PIL \
            --hidden-import PIL.Image \
            --hidden-import PIL.ImageTk \
            --distpath dist/windows \
            --workpath build/windows \
            --specpath .build-cache/specs-windows \
            pdf_ikkcu.py
    "

echo "[windows] 완료."
ls -lh "${OUT_DIR}/PDF.ikkcu_Tools.exe" 2>/dev/null || ls -lh "$OUT_DIR/"
