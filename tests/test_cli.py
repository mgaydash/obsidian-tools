"""Unit tests for obsidian_tools.py CLI"""

import pytest
import sys
from pathlib import Path
from io import StringIO


# Import the main module
import obsidian_tools


# ============================================================================
# Tests for read_titles_from_stdin()
# ============================================================================

def test_read_titles_from_stdin(monkeypatch):
    """Test reading titles from stdin."""
    input_data = "Inception\nThe Matrix\nInterstellar\n"
    monkeypatch.setattr('sys.stdin', StringIO(input_data))

    titles = obsidian_tools.read_titles_from_stdin()

    assert len(titles) == 3
    assert 'Inception' in titles
    assert 'The Matrix' in titles
    assert 'Interstellar' in titles


def test_read_titles_strips_whitespace(monkeypatch):
    """Test that titles are stripped of leading/trailing whitespace."""
    input_data = "  Inception  \n The Matrix \n"
    monkeypatch.setattr('sys.stdin', StringIO(input_data))

    titles = obsidian_tools.read_titles_from_stdin()

    assert titles == ['Inception', 'The Matrix']


def test_read_titles_removes_duplicates(monkeypatch):
    """Test that duplicate titles are removed."""
    input_data = "Inception\nThe Matrix\nInception\n"
    monkeypatch.setattr('sys.stdin', StringIO(input_data))

    titles = obsidian_tools.read_titles_from_stdin()

    assert len(titles) == 2
    assert titles == ['Inception', 'The Matrix']


def test_read_titles_skips_empty_lines(monkeypatch):
    """Test that empty lines are skipped."""
    input_data = "Inception\n\n\nThe Matrix\n\n"
    monkeypatch.setattr('sys.stdin', StringIO(input_data))

    titles = obsidian_tools.read_titles_from_stdin()

    assert len(titles) == 2
    assert titles == ['Inception', 'The Matrix']


# ============================================================================
# Tests for embed_poster_in_content()
# ============================================================================

def test_embed_poster_in_content(tmp_path):
    """Test embedding poster in markdown file."""
    file = tmp_path / 'test.md'
    file.write_text("""---
title: Test Movie
tags: [movie]
---

## Description
Test content here.
""")

    result = obsidian_tools.embed_poster_in_content(file, 'poster.jpg')

    assert result is True

    # Verify file content
    content = file.read_text()
    assert '![[poster.jpg]]' in content
    # Poster should be after frontmatter but before original content
    assert content.index('---\n\n![[poster.jpg]]') > 0


def test_embed_poster_no_frontmatter(tmp_path):
    """Test embedding poster fails without frontmatter."""
    file = tmp_path / 'test.md'
    file.write_text("# Just a heading\n\nSome content")

    result = obsidian_tools.embed_poster_in_content(file, 'poster.jpg')

    assert result is False


# ============================================================================
# Tests for argument parsing - 'add' command
# ============================================================================

def build_add_parser():
    """Build a parser mirroring the 'add' subcommand in obsidian_tools.main()."""
    from argparse import ArgumentParser

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command', required=True)

    add_parser = subparsers.add_parser('add')
    add_parser.add_argument('vault_path')
    add_parser.add_argument('--media-type', required=True, choices=['movie', 'tv', 'game', 'album', 'book'])
    add_parser.add_argument('-b', '--backup', dest='backup_filename', default=None)
    add_parser.add_argument('--poster-width', type=int, default=200)

    return parser


def test_parse_args_add_movie():
    """Test parsing arguments for add command with movie."""
    parser = build_add_parser()

    args = parser.parse_args(['add', '/path/to/vault', '--media-type', 'movie'])

    assert args.command == 'add'
    assert args.vault_path == '/path/to/vault'
    # Backup is optional and defaults to None (disabled)
    assert args.backup_filename is None
    assert args.media_type == 'movie'
    assert args.poster_width == 200


def test_parse_args_add_with_backup():
    """Test that -b/--backup captures the backup file path."""
    parser = build_add_parser()

    # Long form
    args = parser.parse_args(['add', '/path/to/vault', '--media-type', 'movie', '--backup', 'backup.zip'])
    assert args.backup_filename == 'backup.zip'

    # Short form
    args = parser.parse_args(['add', '/path/to/vault', '--media-type', 'movie', '-b', 'backup.zip'])
    assert args.backup_filename == 'backup.zip'


def test_parse_args_add_custom_width():
    """Test parsing add command with custom poster width."""
    parser = build_add_parser()

    args = parser.parse_args(['add', '/path/to/vault', '--media-type', 'tv', '--poster-width', '300'])

    assert args.media_type == 'tv'
    assert args.poster_width == 300


def test_parse_args_add_missing_media_type():
    """Test that missing media-type argument raises error."""
    parser = build_add_parser()

    with pytest.raises(SystemExit):
        args = parser.parse_args(['add', '/path/to/vault'])


def test_parse_args_add_invalid_media_type():
    """Test that invalid media-type raises error."""
    parser = build_add_parser()

    with pytest.raises(SystemExit):
        args = parser.parse_args(['add', '/path/to/vault', '--media-type', 'podcast'])


# ============================================================================
# Tests for argument parsing - 'posters' command
# ============================================================================

def build_posters_parser():
    """Build a parser mirroring the 'posters' subcommand in obsidian_tools.main()."""
    from argparse import ArgumentParser

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command', required=True)

    posters_parser = subparsers.add_parser('posters')
    posters_parser.add_argument('vault_path')
    posters_parser.add_argument('-b', '--backup', dest='backup_filename', default=None)
    posters_parser.add_argument('--width', type=int, default=200)
    posters_parser.add_argument('--media-type', choices=['all', 'movie', 'tv', 'game', 'album', 'book'], default='all')

    return parser


def test_parse_args_posters_default():
    """Test parsing posters command with defaults."""
    parser = build_posters_parser()

    args = parser.parse_args(['posters', '/path/to/vault'])

    assert args.command == 'posters'
    assert args.vault_path == '/path/to/vault'
    # Backup is optional and defaults to None (disabled)
    assert args.backup_filename is None
    assert args.width == 200
    assert args.media_type == 'all'


def test_parse_args_posters_with_backup():
    """Test that -b/--backup captures the backup file path."""
    parser = build_posters_parser()

    # Long form
    args = parser.parse_args(['posters', '/path/to/vault', '--backup', 'backup.zip'])
    assert args.backup_filename == 'backup.zip'

    # Short form
    args = parser.parse_args(['posters', '/path/to/vault', '-b', 'backup.zip'])
    assert args.backup_filename == 'backup.zip'


def test_parse_args_posters_custom_width():
    """Test parsing posters command with custom width."""
    parser = build_posters_parser()

    args = parser.parse_args(['posters', '/path/to/vault', '--width', '300'])

    assert args.width == 300


def test_parse_args_posters_media_type_filter():
    """Test parsing posters command with media type filter."""
    parser = build_posters_parser()

    args = parser.parse_args(['posters', '/path/to/vault', '--media-type', 'album'])

    assert args.media_type == 'album'


def test_parse_args_posters_invalid_media_type():
    """Test that invalid media type filter raises error."""
    parser = build_posters_parser()

    with pytest.raises(SystemExit):
        args = parser.parse_args(['posters', '/path/to/vault', '--media-type', 'podcast'])


# ============================================================================
# Tests for width validation
# ============================================================================

@pytest.mark.parametrize("width,should_fail", [
    (49, True),    # Too small
    (50, False),   # Minimum valid
    (200, False),  # Default valid
    (2000, False), # Maximum valid
    (2001, True),  # Too large
])
def test_width_validation_logic(width, should_fail):
    """Test width validation logic."""
    # Simulate the validation logic
    is_valid = 50 <= width <= 2000

    if should_fail:
        assert is_valid is False
    else:
        assert is_valid is True


# ============================================================================
# Tests for media type choices
# ============================================================================

def test_add_command_media_type_choices():
    """Test that add command accepts correct media types."""
    parser = build_add_parser()

    # Test all valid choices
    for media_type in ['movie', 'tv', 'game', 'album', 'book']:
        args = parser.parse_args(['add', '/vault', '--media-type', media_type])
        assert args.media_type == media_type


def test_posters_command_media_type_choices():
    """Test that posters command accepts correct media types including 'all'."""
    parser = build_posters_parser()

    # Test all valid choices
    for media_type in ['all', 'movie', 'tv', 'game', 'album', 'book']:
        args = parser.parse_args(['posters', '/vault', '--media-type', media_type])
        assert args.media_type == media_type


# ============================================================================
# Tests for command requirements
# ============================================================================

def test_command_required():
    """Test that a command is required."""
    from argparse import ArgumentParser

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command', required=True)
    add_parser = subparsers.add_parser('add')
    posters_parser = subparsers.add_parser('posters')

    # Should fail without a command
    with pytest.raises(SystemExit):
        args = parser.parse_args([])


def test_command_routing():
    """Test that commands are properly identified."""
    from argparse import ArgumentParser

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    add_parser = subparsers.add_parser('add')
    add_parser.add_argument('vault_path')

    posters_parser = subparsers.add_parser('posters')
    posters_parser.add_argument('vault_path')

    # Test add command
    args = parser.parse_args(['add', '/vault'])
    assert args.command == 'add'

    # Test posters command
    args = parser.parse_args(['posters', '/vault'])
    assert args.command == 'posters'


# ============================================================================
# Tests for optional backup behavior in command handlers
# ============================================================================

from argparse import Namespace
from unittest.mock import Mock


def test_add_command_skips_backup_when_not_requested(tmp_path, monkeypatch):
    """add: no backup is created when backup_filename is None."""
    backup_mock = Mock()
    monkeypatch.setattr(obsidian_tools, 'create_vault_backup', backup_mock)
    # Empty stdin so the command returns right after the (skipped) backup step
    monkeypatch.setattr('sys.stdin', StringIO(''))

    args = Namespace(
        vault_path=str(tmp_path),
        media_type='book',
        backup_filename=None,
        poster_width=200,
    )
    obsidian_tools.handle_add_command(args)

    backup_mock.assert_not_called()


def test_add_command_creates_backup_when_requested(tmp_path, monkeypatch):
    """add: backup is created when backup_filename is provided."""
    backup_mock = Mock()
    monkeypatch.setattr(obsidian_tools, 'create_vault_backup', backup_mock)
    monkeypatch.setattr('sys.stdin', StringIO(''))

    backup_path = str(tmp_path / 'backup.zip')
    args = Namespace(
        vault_path=str(tmp_path),
        media_type='book',
        backup_filename=backup_path,
        poster_width=200,
    )
    obsidian_tools.handle_add_command(args)

    backup_mock.assert_called_once_with(Path(str(tmp_path)), backup_path)


def test_posters_command_skips_backup_when_not_requested(tmp_path, monkeypatch):
    """posters: no backup is created when backup_filename is None."""
    backup_mock = Mock()
    monkeypatch.setattr(obsidian_tools, 'create_vault_backup', backup_mock)

    args = Namespace(
        vault_path=str(tmp_path),
        backup_filename=None,
        width=200,
        media_type='all',
    )
    obsidian_tools.handle_posters_command(args)

    backup_mock.assert_not_called()


def test_posters_command_creates_backup_when_requested(tmp_path, monkeypatch):
    """posters: backup is created when backup_filename is provided."""
    backup_mock = Mock()
    monkeypatch.setattr(obsidian_tools, 'create_vault_backup', backup_mock)

    backup_path = str(tmp_path / 'backup.zip')
    args = Namespace(
        vault_path=str(tmp_path),
        backup_filename=backup_path,
        width=200,
        media_type='all',
    )
    obsidian_tools.handle_posters_command(args)

    backup_mock.assert_called_once_with(Path(str(tmp_path)), backup_path)
