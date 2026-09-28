#!/usr/bin/env python3
"""
Utility to organize files in a directory (by default the user's ~/Downloads folder)
by moving them into sub‑folders based on their file extensions.

Features
--------
* Configurable source directory via ``--src`` (defaults to ~/Downloads).
* ``--dry-run`` – show what would be moved without performing any file operations.
* ``--yes`` – skip confirmation prompts and move everything automatically.
* ``--no‑confirm`` – synonym for ``--yes`` (kept for backward compatibility).
* Extensible mapping of extensions to target folders (easy to modify the
  ``EXTENSION_MAP`` dictionary).
* Safe handling of name collisions – if a file with the same name already exists
  in the destination folder, a numeric suffix is added (e.g. ``file (1).txt``).

The script is deliberately lightweight and has no external dependencies beyond the
standard library.
"""

import argparse
import os
import shutil
from pathlib import Path
from typing import Dict

# --------------------------------------------------------------------------- #
# Extension → folder mapping. Extend or modify as needed.
# --------------------------------------------------------------------------- #
EXTENSION_MAP: Dict[str, str] = {
    ".jpg": "Images",
    ".jpeg": "Images",
    ".png": "Images",
    ".gif": "Images",
    ".pdf": "Documents",
    ".doc": "Documents",
    ".docx": "Documents",
    ".mp4": "Videos",
    ".mov": "Videos",
    ".avi": "Videos",
    ".zip": "Archives",
    ".rar": "Archives",
    ".7z": "Archives",
}


def get_target_folder(extension: str) -> str:
    """Return the folder name for a given file extension."""
    return EXTENSION_MAP.get(extension.lower(), "Other")


def unique_destination(dest: Path) -> Path:
    """
    If ``dest`` already exists, generate a new path by appending a numeric
    suffix before the file extension (e.g. ``file (1).txt``).

    Returns the first non‑existent path.
    """
    if not dest.exists():
        return dest

    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    counter = 1

    while True:
        new_name = f"{stem} ({counter}){suffix}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        counter += 1


def ask_confirmation(src: Path, dest: Path) -> bool:
    """Prompt the user to confirm moving a file."""
    answer = input(
        f"Move '{src.name}' → '{dest.parent.name}/{dest.name}'? [y/N] "
    ).strip().lower()
    return answer in ("y", "yes")


def move_file(src: Path, dest: Path, dry_run: bool = False) -> bool:
    """
    Move ``src`` to ``dest`` (or a unique variant if a name clash occurs).

    Returns ``True`` if the file was (or would be) moved, ``False`` otherwise.
    """
    final_dest = unique_destination(dest)

    if dry_run:
        print(f"[DRY‑RUN] Would move: {src} → {final_dest}")
        return True

    try:
        shutil.move(str(src), str(final_dest))
        print(f"Moved: {src.name} → {final_dest.parent.name}/")
        return True
    except Exception as exc:  # pragma: no cover – defensive
        print(f"Failed to move {src.name}: {exc}")
        return False


def organize_downloads(
    download_path: Path,
    *,
    auto_confirm: bool = False,
    dry_run: bool = False,
) -> None:
    """
    Iterate over files in ``download_path`` and move them according to their
    extension.

    Parameters
    ----------
    download_path: Path
        Directory that will be scanned (non‑recursively).
    auto_confirm: bool, optional
        If ``True`` skip the interactive prompt and move everything.
    dry_run: bool, optional
        If ``True`` only display the actions without touching the filesystem.
    """
    if not download_path.is_dir():
        print(f"Error: {download_path} is not a directory.")
        return

    for item in download_path.iterdir():
        # Skip directories (including the target folders we may have created)
        if item.is_dir():
            continue

        ext = item.suffix.lower()
        target_folder_name = get_target_folder(ext)
        target_folder = download_path / target_folder_name
        target_folder.mkdir(exist_ok=True)

        destination = target_folder / item.name

        if auto_confirm or ask_confirmation(item, destination):
            move_file(item, destination, dry_run=dry_run)
        else:
            print(f"Skipped: {item.name}")


def parse_args() -> argparse.Namespace:
    """Parse command‑line arguments."""
    parser = argparse.ArgumentParser(
        description="Organise files in a directory by moving them into "
        "sub‑folders based on file extensions."
    )
    parser.add_argument(
        "--src",
        type=Path,
        default=Path(os.path.expanduser("~/Downloads")).resolve(),
        help="Source directory to organise (default: ~/Downloads).",
    )
    parser.add_argument(
        "--yes",
        "--no-confirm",
        dest="auto_confirm",
        action="store_true",
        help="Move files without asking for confirmation.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be moved without performing any file operations.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    organize_downloads(
        args.src,
        auto_confirm=args.auto_confirm,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
