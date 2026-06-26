@echo off
setlocal
cd /d "%~dp0.."

echo [1/3] Installing dependencies...
pip install -r build\requirements.txt

echo [2/3] Building Windows EXE...
pyinstaller ^
  --onefile ^
  --windowed ^
  --name "PDF.ikkcu_Tools" ^
  --hidden-import pypdf ^
  --hidden-import pypdf.constants ^
  --hidden-import pypdf.generic ^
  --hidden-import fitz ^
  --hidden-import pymupdf ^
  --hidden-import PIL ^
  --hidden-import PIL.Image ^
  --hidden-import PIL.ImageTk ^
  --hidden-import PIL.ImageDraw ^
  --hidden-import PIL.ImageFont ^
  --hidden-import cryptography ^
  --hidden-import cryptography.hazmat.primitives.ciphers ^
  --hidden-import cryptography.hazmat.primitives.ciphers.algorithms ^
  --hidden-import cryptography.hazmat.primitives.ciphers.modes ^
  --hidden-import cryptography.hazmat.backends ^
  --hidden-import cryptography.hazmat.backends.openssl ^
  --collect-all cryptography ^
  pdf_ikkcu.py

echo [3/3] Done.
echo Output: dist\PDF.ikkcu_Tools.exe
pause
