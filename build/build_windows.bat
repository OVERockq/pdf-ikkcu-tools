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
  --hidden-import fitz ^
  --hidden-import pymupdf ^
  --hidden-import PIL ^
  --hidden-import PIL.Image ^
  --hidden-import PIL.ImageTk ^
  pdf_ikkcu.py

echo [3/3] Done.
echo Output: dist\PDF.ikkcu_Tools.exe
pause
