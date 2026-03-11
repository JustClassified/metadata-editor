# Usage Guide

## Typical session

1. Launch `metadata-editor`.
2. Enter (or pass) a valid image folder.
3. Refresh list and select an image.
4. Create a backup before edits.
5. Edit one field or run batch edit.
6. Export image JSON and optional folder summary.

## Batch workflow (new)

1. Choose **Batch edit metadata**.
2. Pick image type (`JPEG`, `TIFF`, `WEBP`, `PNG`).
3. Select multiple files using comma-separated indexes.
4. Pick field/key and value.
5. Confirm to apply updates.

## Safety recommendations

- Always run **Create backup** before large changes.
- Use **Strip editable metadata** only after confirmation.
- Export `metadata-summary.json` before and after batch edits.

## Extending EXIF fields

Add more EXIF tags by extending `EDITABLE_EXIF_FIELDS` in `metadata_editor/cli.py`.
Use constants from `piexif.ImageIFD` / `piexif.ExifIFD` for correct tag IDs.
