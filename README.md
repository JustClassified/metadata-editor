# Metadata Editor (Python CLI)

A robust **terminal-first** image metadata editor with a cleaner interactive design.

## Features

- Browse/select images from a folder
- Search filenames and select quickly
- View metadata (type, file details, editable tags)
- Edit EXIF fields (JPEG/TIFF/WEBP)
- Edit PNG text metadata keys
- **Batch edit metadata** across multiple images
- Create backup files before edits
- Export single-image metadata to JSON
- Clone metadata to another compatible image
- Strip editable metadata from current image
- Export full-folder metadata summary (`metadata-summary.json`)

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run

```bash
metadata-editor
```

Or specify a startup folder:

```bash
metadata-editor --folder /path/to/images
```

## Main menu overview

1. Refresh image list
2. Select image
3. Search + select image
4. View metadata
5. Create backup
6. Edit metadata field
7. Batch edit metadata
8. Export metadata to JSON
9. Clone metadata to another image
10. Strip editable metadata
11. Export folder metadata summary
12. Change folder
0. Exit

## Supported formats

- JPEG / JPG
- PNG
- TIFF
- WEBP

## Default editable EXIF fields

- Image Description
- Artist
- Software
- Copyright
- Date Time
- Lens Make
- Lens Model
- User Comment

## Safety design

- Explicit confirmation before destructive actions
- Sidecar backup creation (`<file>.<ext>.bak`)
- Type-compatible metadata cloning only
- JSON exports for auditing and rollback workflows

## Developer checks

```bash
python -m compileall metadata_editor
python -m metadata_editor.cli --help
```
