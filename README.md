# PDF ikkcu

PDF ikkcu is a desktop PDF utility built with Python and Tkinter.

## Features

- Encrypt PDFs with AES-256, AES-128, or RC4-128.
- Edit page order with thumbnail previews.
- Delete, append, and extract pages.
- Merge multiple PDFs.
- Split PDFs by page, range, or fixed page count.
- Compress PDF content streams and optionally remove metadata.

## Requirements

- Python 3.12+ recommended.
- Tkinter support in the local Python install.

Install runtime and packaging dependencies:

```sh
python3 -m pip install -r build/requirements.txt -r requirements.txt
```

## Run

```sh
python3 pdf_ikkcu.py
```

The app allows multiple instances. Closing a window cleans up only that app process.

## Test

```sh
python3 -m unittest discover -s tests
python3 -m py_compile pdf_ikkcu.py tests/test_pdf_ikkcu.py
```

## Build

macOS:

```sh
bash build/build_mac.sh
```

Output:

- `dist/PDF ikkcu.app`
- `PDF_ikkcu_mac.dmg`

Linux amd64:

```sh
bash build/build_linux.sh
```

Output:

- `dist/pdf_ikkcu`
- `dist/pdf-ikkcu_1.0.0_amd64.deb`

Windows:

```bat
build\build_windows.bat
```

PyInstaller builds should be run on the target operating system. The Windows EXE should be produced on Windows.

## Repository Notes

Generated artifacts are intentionally ignored:

- `dist/`
- `.build-cache/`
- `*.dmg`
- `*.spec`
- `__pycache__/`

Local agent memory under `ai-memory/` is also ignored.
