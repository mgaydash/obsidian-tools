"""Backup utilities for Obsidian vault."""

import os
import zipfile
from pathlib import Path


def create_vault_backup(vault_path: Path, backup_filename: str) -> None:
    """Create a zip backup of the vault."""
    print(f"Creating backup: {backup_filename}")
    with zipfile.ZipFile(backup_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(vault_path):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(vault_path)
                zipf.write(file_path, arcname)
    print(f"✓ Backup created successfully\n")
