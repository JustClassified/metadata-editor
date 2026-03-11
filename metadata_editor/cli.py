"""Terminal-first image metadata editor.

This module provides an interactive CLI designed for shell-only environments.
It supports inspecting and editing common metadata fields for JPEG/TIFF/WEBP
(EXIF) and PNG (text chunks), with safety-focused helpers like backups,
metadata export, batch updates, and metadata stripping.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import piexif
except ModuleNotFoundError:  # pragma: no cover - depends on environment setup
    piexif = None

try:
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
except ModuleNotFoundError:  # pragma: no cover - depends on environment setup
    Image = None
    PngInfo = None

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
EDITABLE_EXIF_FIELDS: Dict[str, Tuple[str, int]] = {}


@dataclass
class SessionContext:
    """Tracks session-level locations and current image choice."""

    folder: Path
    image_paths: List[Path]
    selected_image: Optional[Path] = None


def ensure_dependencies() -> None:
    """Raise a helpful error if runtime dependencies are missing."""
    missing = []
    if piexif is None:
        missing.append("piexif")
    if Image is None or PngInfo is None:
        missing.append("Pillow")
    if missing:
        raise SystemExit(
            f"Missing runtime dependencies: {', '.join(missing)}. "
            "Install with: pip install -e ."
        )


def init_editable_fields() -> None:
    """Populate editable EXIF field map once dependencies are available."""
    if EDITABLE_EXIF_FIELDS:
        return

    EDITABLE_EXIF_FIELDS.update(
        {
            "Image Description": ("0th", piexif.ImageIFD.ImageDescription),
            "Artist": ("0th", piexif.ImageIFD.Artist),
            "Software": ("0th", piexif.ImageIFD.Software),
            "Copyright": ("0th", piexif.ImageIFD.Copyright),
            "Date Time": ("0th", piexif.ImageIFD.DateTime),
            "Lens Make": ("Exif", piexif.ExifIFD.LensMake),
            "Lens Model": ("Exif", piexif.ExifIFD.LensModel),
            "User Comment": ("Exif", piexif.ExifIFD.UserComment),
        }
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for startup defaults."""
    parser = argparse.ArgumentParser(
        prog="metadata-editor",
        description="Interactive image metadata editor for EXIF and PNG text chunks.",
    )
    parser.add_argument("--folder", type=Path, help="Optional startup folder containing images.")
    return parser.parse_args()


def print_banner() -> None:
    """Print a concise startup banner."""
    print("=" * 72)
    print(" Image Metadata Editor (CLI)")
    print(" Inspect, edit, batch-update, clone, strip, and export metadata")
    print("=" * 72)


def confirm(prompt: str) -> bool:
    """Ask a yes/no confirmation prompt."""
    return input(f"{prompt} [y/N]: ").strip().lower() in {"y", "yes"}


def discover_images(folder: Path) -> List[Path]:
    """Return sorted image files in *folder* filtered by known extensions."""
    return sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS],
        key=lambda p: p.name.lower(),
    )


def choose_from_list(title: str, options: List[str]) -> Optional[int]:
    """Display a numbered menu and return selected index or ``None``."""
    if not options:
        print("No options available.")
        return None

    print(f"\n{title}")
    print("-" * len(title))
    for idx, option in enumerate(options, start=1):
        print(f" {idx:>2}. {option}")
    print("  0. Cancel")

    while True:
        raw = input("Choose an option: ").strip()
        if raw == "0":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print("Invalid selection. Enter a listed number.")


def choose_many_from_list(title: str, options: List[str]) -> List[int]:
    """Select multiple indexes with comma-separated input."""
    if not options:
        print("No options available.")
        return []

    print(f"\n{title}")
    print("-" * len(title))
    for idx, option in enumerate(options, start=1):
        print(f" {idx:>2}. {option}")
    print("Enter indices separated by commas (example: 1,3,5) or leave blank to cancel.")

    raw = input("Select images: ").strip()
    if not raw:
        return []

    selected: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= len(options):
            idx = int(part) - 1
            if idx not in selected:
                selected.append(idx)
    return selected


def prompt_folder(initial: Optional[Path] = None) -> Path:
    """Prompt until the user provides an existing directory."""
    if initial and initial.is_dir():
        return initial

    while True:
        raw = input("Enter image folder path: ").strip()
        folder = Path(raw).expanduser()
        if folder.is_dir():
            return folder
        print("Folder not found. Try again.")


def detect_image_type(path: Path) -> str:
    """Return a normalized image format string based on file content."""
    with Image.open(path) as img:
        return (img.format or path.suffix.replace(".", "")).upper()


def load_exif(path: Path) -> Dict[str, dict]:
    """Load EXIF for an image and return a safe empty structure when missing."""
    try:
        return piexif.load(str(path))
    except piexif.InvalidImageDataError:
        return {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}


def read_metadata(path: Path) -> Dict[str, str]:
    """Read image metadata into a flat dictionary for display/export."""
    metadata: Dict[str, str] = {}
    image_type = detect_image_type(path)
    stat = path.stat()
    metadata["Image Type"] = image_type
    metadata["File Size (bytes)"] = str(stat.st_size)
    metadata["Modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")

    if image_type in {"JPEG", "TIFF", "WEBP"}:
        exif_dict = load_exif(path)
        for label, (ifd_name, tag_id) in EDITABLE_EXIF_FIELDS.items():
            raw_value = exif_dict.get(ifd_name, {}).get(tag_id)
            if raw_value is None:
                continue
            metadata[label] = raw_value.decode("utf-8", errors="replace") if isinstance(raw_value, bytes) else str(raw_value)
    elif image_type == "PNG":
        with Image.open(path) as img:
            for key, value in img.info.items():
                metadata[f"PNG:{key}"] = str(value)

    return metadata


def display_metadata(path: Path) -> None:
    """Print metadata entries for a selected image."""
    metadata = read_metadata(path)
    print(f"\nMetadata for: {path.name}")
    print("-" * (14 + len(path.name)))
    for key, value in metadata.items():
        print(f"{key:>20}: {value}")


def create_backup(path: Path) -> Path:
    """Create a sidecar backup copy with *.bak* suffix."""
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    return backup


def edit_exif_field(path: Path) -> None:
    """Interactive flow for editing one supported EXIF field."""
    options = list(EDITABLE_EXIF_FIELDS.keys())
    idx = choose_from_list("Editable EXIF fields", options)
    if idx is None:
        return

    field_name = options[idx]
    new_value = input(f"New value for '{field_name}' (blank to clear): ")
    apply_exif_update(path, field_name, new_value)
    print(f"Updated '{field_name}' on {path.name}.")


def apply_exif_update(path: Path, field_name: str, new_value: str) -> None:
    """Apply a single EXIF field update to an image path."""
    exif_dict = load_exif(path)
    ifd_name, tag_id = EDITABLE_EXIF_FIELDS[field_name]

    if new_value:
        encoded = new_value.encode("utf-8")
        if field_name == "User Comment":
            encoded = b"ASCII\x00\x00\x00" + new_value.encode("ascii", errors="replace")
        exif_dict.setdefault(ifd_name, {})[tag_id] = encoded
    else:
        exif_dict.setdefault(ifd_name, {}).pop(tag_id, None)

    piexif.insert(piexif.dump(exif_dict), str(path))


def edit_png_text_field(path: Path) -> None:
    """Edit or add PNG text metadata keys by rewriting the PNG file."""
    with Image.open(path) as img:
        existing = {k: str(v) for k, v in img.info.items()}
        print("\nCurrent PNG text metadata:")
        if existing:
            for key, value in existing.items():
                print(f" - {key}: {value}")
        else:
            print(" (none)")

        key = input("Text key to edit (e.g., Description, Author): ").strip()
        if not key:
            print("No key provided. Aborting.")
            return
        value = input("New value (blank to remove key): ")
        apply_png_update(path, key, value)

    print(f"Updated PNG text metadata key '{key}' on {path.name}.")


def apply_png_update(path: Path, key: str, value: str) -> None:
    """Apply one PNG key update by rebuilding PNG text chunks."""
    with Image.open(path) as img:
        existing = {k: str(v) for k, v in img.info.items()}
        if value:
            existing[key] = value
        else:
            existing.pop(key, None)

        pnginfo = PngInfo()
        for k, v in existing.items():
            pnginfo.add_text(k, v)

        img.copy().save(path, pnginfo=pnginfo)


def export_metadata_json(path: Path) -> None:
    """Export metadata to a JSON file next to the image."""
    export_path = path.with_suffix(path.suffix + ".metadata.json")
    export_path.write_text(json.dumps(read_metadata(path), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Metadata exported to: {export_path}")


def clone_metadata(source: Path, destination: Path) -> None:
    """Copy metadata from source image to destination when formats match."""
    source_type = detect_image_type(source)
    destination_type = detect_image_type(destination)
    if source_type != destination_type:
        print("Source and destination image types differ. Clone cancelled.")
        return

    if source_type in {"JPEG", "TIFF", "WEBP"}:
        piexif.insert(piexif.dump(load_exif(source)), str(destination))
    elif source_type == "PNG":
        with Image.open(source) as src, Image.open(destination) as dst:
            pnginfo = PngInfo()
            for key, value in src.info.items():
                pnginfo.add_text(key, str(value))
            dst.copy().save(destination, pnginfo=pnginfo)

    print(f"Metadata cloned from {source.name} -> {destination.name}")


def strip_editable_metadata(path: Path) -> None:
    """Remove editable metadata fields from the selected image."""
    image_type = detect_image_type(path)
    if image_type in {"JPEG", "TIFF", "WEBP"}:
        exif_dict = load_exif(path)
        for ifd_name, tag_id in EDITABLE_EXIF_FIELDS.values():
            exif_dict.setdefault(ifd_name, {}).pop(tag_id, None)
        piexif.insert(piexif.dump(exif_dict), str(path))
    elif image_type == "PNG":
        with Image.open(path) as img:
            img.copy().save(path, pnginfo=PngInfo())
    print(f"Removed editable metadata from {path.name}.")


def export_folder_report(context: SessionContext) -> None:
    """Export metadata summary for all discovered images to JSON."""
    report = {p.name: read_metadata(p) for p in context.image_paths}
    export_path = context.folder / "metadata-summary.json"
    export_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Folder metadata summary written: {export_path}")


def select_image(context: SessionContext, filter_term: Optional[str] = None) -> None:
    """Prompt user to select an image; supports optional filename filtering."""
    candidates = context.image_paths
    if filter_term:
        lowered = filter_term.lower()
        candidates = [p for p in context.image_paths if lowered in p.name.lower()]

    idx = choose_from_list(f"Images in {context.folder}", [p.name for p in candidates])
    if idx is not None:
        context.selected_image = candidates[idx]
        print(f"Selected: {context.selected_image.name}")


def refresh_images(context: SessionContext) -> None:
    """Rescan folder for images and keep selection if still present."""
    previous = context.selected_image
    context.image_paths = discover_images(context.folder)
    if previous not in context.image_paths:
        context.selected_image = None


def batch_edit(context: SessionContext) -> None:
    """Apply a single metadata update to multiple images of same type."""
    if not context.image_paths:
        print("No images to batch-edit.")
        return

    image_type = input("Batch target type (JPEG/TIFF/WEBP/PNG): ").strip().upper()
    if image_type not in {"JPEG", "TIFF", "WEBP", "PNG"}:
        print("Unsupported type.")
        return

    targets = [p for p in context.image_paths if detect_image_type(p) == image_type]
    if not targets:
        print(f"No images of type {image_type} found.")
        return

    selected_indexes = choose_many_from_list("Select batch target images", [p.name for p in targets])
    if not selected_indexes:
        print("No images selected.")
        return
    selected_paths = [targets[i] for i in selected_indexes]

    if image_type == "PNG":
        key = input("PNG text key to set: ").strip()
        if not key:
            print("No key provided.")
            return
        value = input("Value (blank removes key): ")
        if not confirm(f"Apply PNG key '{key}' update to {len(selected_paths)} files?"):
            print("Cancelled.")
            return
        for path in selected_paths:
            apply_png_update(path, key, value)
    else:
        field_options = list(EDITABLE_EXIF_FIELDS.keys())
        idx = choose_from_list("Choose EXIF field for batch update", field_options)
        if idx is None:
            return
        field_name = field_options[idx]
        value = input(f"Value for '{field_name}' (blank clears): ")
        if not confirm(f"Apply EXIF update to {len(selected_paths)} files?"):
            print("Cancelled.")
            return
        for path in selected_paths:
            apply_exif_update(path, field_name, value)

    print(f"Batch update complete: {len(selected_paths)} files modified.")


def run_main_loop(context: SessionContext) -> None:
    """Primary menu loop handling metadata management workflows."""
    while True:
        selected = context.selected_image.name if context.selected_image else "(none)"
        print("\nMain Menu")
        print("---------")
        print(f"Current folder : {context.folder}")
        print(f"Selected image : {selected}")
        print(" 1. Refresh image list")
        print(" 2. Select image")
        print(" 3. Search + select image")
        print(" 4. View metadata")
        print(" 5. Create backup")
        print(" 6. Edit metadata field")
        print(" 7. Batch edit metadata")
        print(" 8. Export metadata to JSON")
        print(" 9. Clone metadata to another image")
        print("10. Strip editable metadata")
        print("11. Export folder metadata summary")
        print("12. Change folder")
        print(" 0. Exit")

        choice = input("Choose an option: ").strip()

        if choice == "0":
            print("Goodbye!")
            return
        if choice == "1":
            refresh_images(context)
            print(f"Found {len(context.image_paths)} images.")
            continue
        if choice == "2":
            select_image(context)
            continue
        if choice == "3":
            term = input("Filename search term: ").strip()
            if term:
                select_image(context, filter_term=term)
            continue
        if choice == "7":
            batch_edit(context)
            continue
        if choice == "11":
            export_folder_report(context)
            continue
        if choice == "12":
            context.folder = prompt_folder()
            context.image_paths = discover_images(context.folder)
            context.selected_image = None
            print(f"Folder changed. Found {len(context.image_paths)} images.")
            continue

        if not context.selected_image:
            print("Select an image first.")
            continue

        path = context.selected_image
        if choice == "4":
            display_metadata(path)
        elif choice == "5":
            print(f"Backup created: {create_backup(path)}")
        elif choice == "6":
            image_type = detect_image_type(path)
            if image_type == "PNG":
                edit_png_text_field(path)
            elif image_type in {"JPEG", "TIFF", "WEBP"}:
                edit_exif_field(path)
            else:
                print(f"Unsupported image type for edit: {image_type}")
        elif choice == "8":
            export_metadata_json(path)
        elif choice == "9":
            others = [p for p in context.image_paths if p != path]
            idx = choose_from_list("Select destination image", [p.name for p in others])
            if idx is not None:
                clone_metadata(path, others[idx])
        elif choice == "10":
            if confirm(f"Remove editable metadata from {path.name}?"):
                strip_editable_metadata(path)
            else:
                print("Cancelled.")
        else:
            print("Unknown option.")


def main() -> None:
    """Entry point for the metadata editor CLI."""
    args = parse_args()
    ensure_dependencies()
    init_editable_fields()
    print_banner()

    folder = prompt_folder(args.folder)
    image_paths = discover_images(folder)
    print(f"Loaded {len(image_paths)} image(s) from {folder}")
    run_main_loop(SessionContext(folder=folder, image_paths=image_paths))


if __name__ == "__main__":
    main()
