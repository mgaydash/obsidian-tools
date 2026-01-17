"""Unit tests for lib/backup.py"""

import pytest
import zipfile
from pathlib import Path

from lib.backup import create_vault_backup


# ============================================================================
# Tests for create_vault_backup
# ============================================================================

def test_create_vault_backup_success(tmp_path, capsys):
    """Test successful backup creation."""
    # Create a test vault with some files
    vault = tmp_path / "vault"
    vault.mkdir()

    # Create test files
    (vault / "note1.md").write_text("# Note 1")
    (vault / "note2.md").write_text("# Note 2")

    # Create subdirectory with file
    subdir = vault / "subfolder"
    subdir.mkdir()
    (subdir / "note3.md").write_text("# Note 3")

    # Create backup
    backup_path = tmp_path / "backup.zip"
    create_vault_backup(vault, str(backup_path))

    # Verify backup was created
    assert backup_path.exists()

    # Verify backup contents
    with zipfile.ZipFile(backup_path, 'r') as zipf:
        names = zipf.namelist()
        assert 'note1.md' in names
        assert 'note2.md' in names
        assert 'subfolder/note3.md' in names

        # Verify file contents
        assert zipf.read('note1.md').decode() == "# Note 1"
        assert zipf.read('note2.md').decode() == "# Note 2"
        assert zipf.read('subfolder/note3.md').decode() == "# Note 3"

    # Verify console output
    captured = capsys.readouterr()
    assert 'Creating backup' in captured.out
    assert 'Backup created successfully' in captured.out


def test_create_vault_backup_empty_vault(tmp_path, capsys):
    """Test backup of empty vault."""
    vault = tmp_path / "empty_vault"
    vault.mkdir()

    backup_path = tmp_path / "backup.zip"
    create_vault_backup(vault, str(backup_path))

    # Verify backup was created
    assert backup_path.exists()

    # Verify it's empty
    with zipfile.ZipFile(backup_path, 'r') as zipf:
        assert len(zipf.namelist()) == 0


def test_create_vault_backup_nested_directories(tmp_path):
    """Test backup with deeply nested directory structure."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # Create nested structure: vault/a/b/c/d/file.md
    nested = vault / "a" / "b" / "c" / "d"
    nested.mkdir(parents=True)
    (nested / "deep_file.md").write_text("Deep content")

    # Also create files at each level
    (vault / "root.md").write_text("Root")
    (vault / "a" / "level_a.md").write_text("A")
    (vault / "a" / "b" / "level_b.md").write_text("B")

    backup_path = tmp_path / "backup.zip"
    create_vault_backup(vault, str(backup_path))

    # Verify all files are in backup with correct paths
    with zipfile.ZipFile(backup_path, 'r') as zipf:
        names = zipf.namelist()
        assert 'root.md' in names
        assert 'a/level_a.md' in names
        assert 'a/b/level_b.md' in names
        assert 'a/b/c/d/deep_file.md' in names


def test_create_vault_backup_various_file_types(tmp_path):
    """Test backup with various file types."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # Create different file types
    (vault / "note.md").write_text("# Markdown")
    (vault / "image.jpg").write_bytes(b'fake image data')
    (vault / "config.json").write_text('{"key": "value"}')
    (vault / "data.txt").write_text("Text file")

    backup_path = tmp_path / "backup.zip"
    create_vault_backup(vault, str(backup_path))

    # Verify all file types are backed up
    with zipfile.ZipFile(backup_path, 'r') as zipf:
        names = zipf.namelist()
        assert 'note.md' in names
        assert 'image.jpg' in names
        assert 'config.json' in names
        assert 'data.txt' in names

        # Verify binary data is preserved
        assert zipf.read('image.jpg') == b'fake image data'


def test_create_vault_backup_preserves_relative_paths(tmp_path):
    """Test that backup preserves relative paths from vault root."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # Create structure: Movies/Action/movie.md
    movies = vault / "Movies" / "Action"
    movies.mkdir(parents=True)
    (movies / "movie.md").write_text("# Action Movie")

    backup_path = tmp_path / "backup.zip"
    create_vault_backup(vault, str(backup_path))

    # Verify paths are relative to vault root
    with zipfile.ZipFile(backup_path, 'r') as zipf:
        names = zipf.namelist()
        # Should not include vault name in path
        assert 'Movies/Action/movie.md' in names
        assert not any('vault' in name for name in names)


def test_create_vault_backup_compression(tmp_path):
    """Test that backup uses ZIP compression."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # Create a file with compressible content (repeated text)
    content = "This is repeated text. " * 1000
    (vault / "large.md").write_text(content)

    backup_path = tmp_path / "backup.zip"
    create_vault_backup(vault, str(backup_path))

    # Verify compression
    with zipfile.ZipFile(backup_path, 'r') as zipf:
        info = zipf.getinfo('large.md')
        # Compressed size should be less than uncompressed size
        assert info.compress_size < info.file_size


def test_create_vault_backup_unicode_filenames(tmp_path):
    """Test backup with unicode characters in filenames."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # Create files with unicode names
    (vault / "日本語.md").write_text("Japanese")
    (vault / "émoji🎬.md").write_text("Emoji")
    (vault / "Ñoño.md").write_text("Spanish")

    backup_path = tmp_path / "backup.zip"
    create_vault_backup(vault, str(backup_path))

    # Verify unicode filenames are preserved
    with zipfile.ZipFile(backup_path, 'r') as zipf:
        names = zipf.namelist()
        assert '日本語.md' in names
        assert 'émoji🎬.md' in names
        assert 'Ñoño.md' in names


def test_create_vault_backup_special_characters(tmp_path):
    """Test backup with special characters in filenames."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # Create files with special chars (that are valid on filesystem)
    (vault / "movie (2020).md").write_text("Parentheses")
    (vault / "title - subtitle.md").write_text("Dash")
    (vault / "file's name.md").write_text("Apostrophe")

    backup_path = tmp_path / "backup.zip"
    create_vault_backup(vault, str(backup_path))

    # Verify special chars are preserved
    with zipfile.ZipFile(backup_path, 'r') as zipf:
        names = zipf.namelist()
        assert 'movie (2020).md' in names
        assert 'title - subtitle.md' in names
        assert "file's name.md" in names


def test_create_vault_backup_overwrites_existing(tmp_path):
    """Test that creating backup overwrites existing backup file."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("# Note")

    backup_path = tmp_path / "backup.zip"

    # Create first backup
    create_vault_backup(vault, str(backup_path))
    first_size = backup_path.stat().st_size

    # Add more content
    (vault / "note2.md").write_text("# Note 2 with more content")

    # Create second backup (should overwrite)
    create_vault_backup(vault, str(backup_path))
    second_size = backup_path.stat().st_size

    # Second backup should be larger
    assert second_size > first_size

    # Verify both files are in the backup
    with zipfile.ZipFile(backup_path, 'r') as zipf:
        names = zipf.namelist()
        assert 'note.md' in names
        assert 'note2.md' in names
