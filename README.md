# PDF ikkcu

PDF ikkcu is a desktop PDF utility built with Python and Tkinter.

## Features

### PDF Viewer
- Full PDF reader with single page, continuous scroll, and dual-page (spread) view modes
- Thumbnail side panel for quick page navigation
- Table of contents panel
- Zoom in/out with keyboard shortcuts and toolbar buttons
- AI file (.ai) viewer support

### PDF Editing
- Edit page order with thumbnail previews
- Delete, append, and extract pages (PDF / JPG / PNG output)
- Merge multiple PDFs
- Split PDFs by page, range, or fixed page count

### Security & Stamps
- Encrypt PDFs with AES-256, AES-128, or RC4-128
- Apply custom stamps to pages

### Utilities
- Compress PDF content streams and optionally remove metadata
- Edit document properties (title, author, subject, keywords)
- Preferences dialog (default view mode, shortcuts, default viewer)

### UI
- Native menubar (File / Tools / View / Help)
- PIL-generated toolbar icons

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

- `dist/macos-arm64/PDF ikkcu.app`
- `dist/macos-x86_64/PDF ikkcu.app`
- `PDF.ikkcu_v2.0_mac_arm64.dmg`
- `PDF.ikkcu_Tools_mac_x86_64.dmg`
- `PDF.ikkcu_Tools_mac_universal.dmg`

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
