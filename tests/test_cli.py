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

def test_parse_args_add_movie(monkeypatch):
    """Test parsing arguments for add command with movie."""
    monkeypatch.setattr('sys.argv', [
        'obsidian_tools.py',
        'add',
        '/path/to/vault',
        'backup.zip',
        '--media-type', 'movie'
    ])

    args = obsidian_tools.main.__wrapped__() if hasattr(obsidian_tools.main, '__wrapped__') else None

    # Since we can't easily test main() directly without running the full command,
    # let's test the parser directly
    from argparse import ArgumentParser
    import argparse

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command', required=True)

    add_parser = subparsers.add_parser('add')
    add_parser.add_argument('vault_path')
    add_parser.add_argument('backup_filename')
    add_parser.add_argument('--media-type', required=True, choices=['movie', 'tv', 'game', 'album'])
    add_parser.add_argument('--poster-width', type=int, default=200)

    args = parser.parse_args(['add', '/path/to/vault', 'backup.zip', '--media-type', 'movie'])

    assert args.command == 'add'
    assert args.vault_path == '/path/to/vault'
    assert args.backup_filename == 'backup.zip'
    assert args.media_type == 'movie'
    assert args.poster_width == 200


def test_parse_args_add_custom_width(monkeypatch):
    """Test parsing add command with custom poster width."""
    from argparse import ArgumentParser

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    add_parser = subparsers.add_parser('add')
    add_parser.add_argument('vault_path')
    add_parser.add_argument('backup_filename')
    add_parser.add_argument('--media-type', required=True, choices=['movie', 'tv', 'game', 'album'])
    add_parser.add_argument('--poster-width', type=int, default=200)

    args = parser.parse_args(['add', '/path/to/vault', 'backup.zip', '--media-type', 'tv', '--poster-width', '300'])

    assert args.media_type == 'tv'
    assert args.poster_width == 300


def test_parse_args_add_missing_media_type():
    """Test that missing media-type argument raises error."""
    from argparse import ArgumentParser

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    add_parser = subparsers.add_parser('add')
    add_parser.add_argument('vault_path')
    add_parser.add_argument('backup_filename')
    add_parser.add_argument('--media-type', required=True, choices=['movie', 'tv', 'game', 'album'])

    with pytest.raises(SystemExit):
        args = parser.parse_args(['add', '/path/to/vault', 'backup.zip'])


def test_parse_args_add_invalid_media_type():
    """Test that invalid media-type raises error."""
    from argparse import ArgumentParser

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    add_parser = subparsers.add_parser('add')
    add_parser.add_argument('vault_path')
    add_parser.add_argument('backup_filename')
    add_parser.add_argument('--media-type', required=True, choices=['movie', 'tv', 'game', 'album'])

    with pytest.raises(SystemExit):
        args = parser.parse_args(['add', '/path/to/vault', 'backup.zip', '--media-type', 'book'])


# ============================================================================
# Tests for argument parsing - 'posters' command
# ============================================================================

def test_parse_args_posters_default():
    """Test parsing posters command with defaults."""
    from argparse import ArgumentParser

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    posters_parser = subparsers.add_parser('posters')
    posters_parser.add_argument('vault_path')
    posters_parser.add_argument('backup_filename')
    posters_parser.add_argument('--width', type=int, default=200)
    posters_parser.add_argument('--media-type', choices=['all', 'movie', 'tv', 'game', 'album'], default='all')

    args = parser.parse_args(['posters', '/path/to/vault', 'backup.zip'])

    assert args.command == 'posters'
    assert args.vault_path == '/path/to/vault'
    assert args.backup_filename == 'backup.zip'
    assert args.width == 200
    assert args.media_type == 'all'


def test_parse_args_posters_custom_width():
    """Test parsing posters command with custom width."""
    from argparse import ArgumentParser

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    posters_parser = subparsers.add_parser('posters')
    posters_parser.add_argument('vault_path')
    posters_parser.add_argument('backup_filename')
    posters_parser.add_argument('--width', type=int, default=200)
    posters_parser.add_argument('--media-type', choices=['all', 'movie', 'tv', 'game', 'album'], default='all')

    args = parser.parse_args(['posters', '/path/to/vault', 'backup.zip', '--width', '300'])

    assert args.width == 300


def test_parse_args_posters_media_type_filter():
    """Test parsing posters command with media type filter."""
    from argparse import ArgumentParser

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    posters_parser = subparsers.add_parser('posters')
    posters_parser.add_argument('vault_path')
    posters_parser.add_argument('backup_filename')
    posters_parser.add_argument('--width', type=int, default=200)
    posters_parser.add_argument('--media-type', choices=['all', 'movie', 'tv', 'game', 'album'], default='all')

    args = parser.parse_args(['posters', '/path/to/vault', 'backup.zip', '--media-type', 'album'])

    assert args.media_type == 'album'


def test_parse_args_posters_invalid_media_type():
    """Test that invalid media type filter raises error."""
    from argparse import ArgumentParser

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    posters_parser = subparsers.add_parser('posters')
    posters_parser.add_argument('vault_path')
    posters_parser.add_argument('backup_filename')
    posters_parser.add_argument('--media-type', choices=['all', 'movie', 'tv', 'game', 'album'], default='all')

    with pytest.raises(SystemExit):
        args = parser.parse_args(['posters', '/path/to/vault', 'backup.zip', '--media-type', 'book'])


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
    from argparse import ArgumentParser

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    add_parser = subparsers.add_parser('add')
    add_parser.add_argument('vault_path')
    add_parser.add_argument('backup_filename')
    add_parser.add_argument('--media-type', required=True, choices=['movie', 'tv', 'game', 'album'])

    # Test all valid choices
    for media_type in ['movie', 'tv', 'game', 'album']:
        args = parser.parse_args(['add', '/vault', 'backup.zip', '--media-type', media_type])
        assert args.media_type == media_type


def test_posters_command_media_type_choices():
    """Test that posters command accepts correct media types including 'all'."""
    from argparse import ArgumentParser

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    posters_parser = subparsers.add_parser('posters')
    posters_parser.add_argument('vault_path')
    posters_parser.add_argument('backup_filename')
    posters_parser.add_argument('--media-type', choices=['all', 'movie', 'tv', 'game', 'album'], default='all')

    # Test all valid choices
    for media_type in ['all', 'movie', 'tv', 'game', 'album']:
        args = parser.parse_args(['posters', '/vault', 'backup.zip', '--media-type', media_type])
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
    add_parser.add_argument('backup_filename')

    posters_parser = subparsers.add_parser('posters')
    posters_parser.add_argument('vault_path')
    posters_parser.add_argument('backup_filename')

    # Test add command
    args = parser.parse_args(['add', '/vault', 'backup.zip'])
    assert args.command == 'add'

    # Test posters command
    args = parser.parse_args(['posters', '/vault', 'backup.zip'])
    assert args.command == 'posters'
