# Icon Generation Tool

<p align="center">
  <img src="doc/icon.svg" alt="Icon Generation Tool" width="15%" />
</p>

<p align="center">
  <a href="./README.md">简体中文</a> ·
  <a href="./README.en.md">English</a>
</p>
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" alt="python" />
  <img src="https://img.shields.io/badge/UI-PyQt6%20%2B%20Fluent-4B8BBE" alt="ui" />
</p>


A local `uv + PyQt6` GUI tool to convert common image formats into multi-size `.ico` files (up to `256x256`).

## Features

- Import image files: `png/jpg/jpeg/bmp/webp/tiff/gif`
- Paste image directly with `Ctrl+V`
- Background removal mode switch: `Remove White` / `Remove Black`
- Threshold control `0-255` with a progress indicator
- Cutout mode toggle:
  - When ON, the app applies background transparency using current mode + threshold
  - No extra scaling is applied to the source image in this mode
  - The transparent result is automatically copied to clipboard as PNG
- Export multi-size ICO: `16, 24, 32, 48, 64, 96, 128, 256`
- ICO rendering uses aspect-ratio-preserving scale and center placement (no center-cropping)
- App icon support:
  - Root `icon.ico` is used for the packaged EXE icon
  - Runtime window icon is also set, including Windows title bar top-left icon

## Run With uv

1. Install dependencies

```bash
uv sync
```

2. Launch app

```bash
uv run icon-tool
```

## Build Windows EXE

### Option A: one command script (recommended)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

Optional params:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -SkipSync
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Name MyIconTool -IconPath icon.ico
```

### Option B: manual commands

1. Install build dependencies

```bash
uv sync --extra build
```

2. Build one-file GUI executable

```bash
uv run pyinstaller --noconfirm --clean --onefile --windowed --name IconGenerationTool --icon icon.ico --add-data "icon.ico;." src/icon_tool/app.py
```

## Output

- Executable: `dist/IconGenerationTool.exe` (or `dist/<Name>.exe` if `-Name` is set)

## Files

- `src/icon_tool/app.py`: main app and image processing logic
- `scripts/build.ps1`: one-command Windows build script
- `icon.ico`: app icon used by packaged executable and runtime window
- `pyproject.toml`: project metadata and dependencies