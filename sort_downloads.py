#!/usr/bin/env python3
"""
Script to organize files in the user's ~/Downloads folder by file extension.

- Images:    .jpg, .jpeg, .png, .gif
- Documents: .pdf, .doc, .docx
- Videos:    .mp4, .mov, .avi
- Archives:  .zip, .rar, .7z
- Other:     everything else

For each file the script asks for confirmation before moving it.
"""

import os
import shutil
from pathlib import Path

# Mapping of extensions to target folder names
EXTENSION_MAP = {
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

def ask_confirmation(src: Path, dest: Path) -> bool:
    """Prompt the user to confirm moving a file."""
    answer = input(f"Move '{src.name}' to '{dest.parent.name}'? [y/N] ").strip().lower()
    return answer in ("y", "yes")

def organize_downloads(download_path: Path) -> None:
    """Iterate over files in download_path and move them according to their extension."""
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

        if ask_confirmation(item, destination):
            try:
                shutil.move(str(item), str(destination))
                print(f"Moved: {item.name} → {target_folder_name}/")
            except Exception as e:
                print(f"Failed to move {item.name}: {e}")
        else:
            print(f"Skipped: {item.name}")

def main() -> None:
    downloads_dir = Path(os.path.expanduser("~/Downloads")).resolve()
    organize_downloads(downloads_dir)

if __name__ == "__main__":
    main()
