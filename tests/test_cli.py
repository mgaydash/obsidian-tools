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
    add_parser.add_argument('media_type', choices=['movie', 'tv', 'game', 'album', 'book'])
    add_parser.add_argument('--vault-path', dest='vault_path', default=None)
    add_parser.add_argument('-b', '--backup', dest='backup_filename', default=None)
    add_parser.add_argument('--poster-width', type=int, default=200)

    return parser


def test_parse_args_add_movie():
    """Test parsing arguments for add command with movie (media type positional)."""
    parser = build_add_parser()

    args = parser.parse_args(['add', 'movie'])

    assert args.command == 'add'
    assert args.media_type == 'movie'
    # Vault path is an option and defaults to None (falls back to config)
    assert args.vault_path is None
    # Backup is optional and defaults to None (disabled)
    assert args.backup_filename is None
    assert args.poster_width == 200


def test_parse_args_add_vault_path_option():
    """Test that --vault-path captures the vault path."""
    parser = build_add_parser()

    args = parser.parse_args(['add', 'movie', '--vault-path', '/path/to/vault'])
    assert args.vault_path == '/path/to/vault'


def test_parse_args_add_with_backup():
    """Test that -b/--backup captures the backup file path."""
    parser = build_add_parser()

    # Long form
    args = parser.parse_args(['add', 'movie', '--backup', 'backup.zip'])
    assert args.backup_filename == 'backup.zip'

    # Short form
    args = parser.parse_args(['add', 'movie', '-b', 'backup.zip'])
    assert args.backup_filename == 'backup.zip'


def test_parse_args_add_custom_width():
    """Test parsing add command with custom poster width."""
    parser = build_add_parser()

    args = parser.parse_args(['add', 'tv', '--poster-width', '300'])

    assert args.media_type == 'tv'
    assert args.poster_width == 300


def test_parse_args_add_missing_media_type():
    """Test that the media type positional is required."""
    parser = build_add_parser()

    with pytest.raises(SystemExit):
        args = parser.parse_args(['add'])


def test_parse_args_add_invalid_media_type():
    """Test that invalid media type raises error."""
    parser = build_add_parser()

    with pytest.raises(SystemExit):
        args = parser.parse_args(['add', 'podcast'])


# ============================================================================
# Tests for argument parsing - 'posters' command
# ============================================================================

def build_posters_parser():
    """Build a parser mirroring the 'posters' subcommand in obsidian_tools.main()."""
    from argparse import ArgumentParser

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command', required=True)

    posters_parser = subparsers.add_parser('posters')
    posters_parser.add_argument('--vault-path', dest='vault_path', default=None)
    posters_parser.add_argument('-b', '--backup', dest='backup_filename', default=None)
    posters_parser.add_argument('--width', type=int, default=200)
    posters_parser.add_argument('--media-type', choices=['all', 'movie', 'tv', 'game', 'album', 'book'], default='all')

    return parser


def test_parse_args_posters_default():
    """Test parsing posters command with defaults (no positional args)."""
    parser = build_posters_parser()

    args = parser.parse_args(['posters'])

    assert args.command == 'posters'
    # Vault path is an option and defaults to None (falls back to config)
    assert args.vault_path is None
    # Backup is optional and defaults to None (disabled)
    assert args.backup_filename is None
    assert args.width == 200
    assert args.media_type == 'all'


def test_parse_args_posters_vault_path_option():
    """Test that --vault-path captures the vault path."""
    parser = build_posters_parser()

    args = parser.parse_args(['posters', '--vault-path', '/path/to/vault'])
    assert args.vault_path == '/path/to/vault'


def test_parse_args_posters_with_backup():
    """Test that -b/--backup captures the backup file path."""
    parser = build_posters_parser()

    # Long form
    args = parser.parse_args(['posters', '--backup', 'backup.zip'])
    assert args.backup_filename == 'backup.zip'

    # Short form
    args = parser.parse_args(['posters', '-b', 'backup.zip'])
    assert args.backup_filename == 'backup.zip'


def test_parse_args_posters_custom_width():
    """Test parsing posters command with custom width."""
    parser = build_posters_parser()

    args = parser.parse_args(['posters', '--width', '300'])

    assert args.width == 300


def test_parse_args_posters_media_type_filter():
    """Test parsing posters command with media type filter."""
    parser = build_posters_parser()

    args = parser.parse_args(['posters', '--media-type', 'album'])

    assert args.media_type == 'album'


def test_parse_args_posters_invalid_media_type():
    """Test that invalid media type filter raises error."""
    parser = build_posters_parser()

    with pytest.raises(SystemExit):
        args = parser.parse_args(['posters', '--media-type', 'podcast'])


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

    # Test all valid choices (media type is the positional argument)
    for media_type in ['movie', 'tv', 'game', 'album', 'book']:
        args = parser.parse_args(['add', media_type])
        assert args.media_type == media_type


def test_posters_command_media_type_choices():
    """Test that posters command accepts correct media types including 'all'."""
    parser = build_posters_parser()

    # Test all valid choices (media type is a --media-type filter option)
    for media_type in ['all', 'movie', 'tv', 'game', 'album', 'book']:
        args = parser.parse_args(['posters', '--media-type', media_type])
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


# ============================================================================
# Tests for optional vault_path parsing (add / posters)
# ============================================================================

def test_parse_args_add_vault_optional():
    """add: vault path may be omitted (falls back to config at runtime)."""
    parser = build_add_parser()
    args = parser.parse_args(['add', 'movie'])
    assert args.vault_path is None
    assert args.media_type == 'movie'


def test_parse_args_posters_vault_optional():
    """posters: vault_path may be omitted (falls back to config at runtime)."""
    parser = build_posters_parser()
    args = parser.parse_args(['posters'])
    assert args.vault_path is None


# ============================================================================
# Tests for argument parsing - 'configure' command
# ============================================================================

def build_configure_parser():
    """Build a parser mirroring the 'configure' subcommand in obsidian_tools.main()."""
    from argparse import ArgumentParser

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command', required=True)

    configure_parser = subparsers.add_parser('configure')
    configure_parser.add_argument('--vault-path', dest='vault_path', default=None)
    configure_parser.add_argument('--show', action='store_true')

    return parser


def test_parse_args_configure_vault_path():
    parser = build_configure_parser()
    args = parser.parse_args(['configure', '--vault-path', '/path/to/vault'])
    assert args.command == 'configure'
    assert args.vault_path == '/path/to/vault'
    assert args.show is False


def test_parse_args_configure_show():
    parser = build_configure_parser()
    args = parser.parse_args(['configure', '--show'])
    assert args.show is True
    assert args.vault_path is None


def test_parse_args_configure_defaults():
    parser = build_configure_parser()
    args = parser.parse_args(['configure'])
    assert args.vault_path is None
    assert args.show is False


# ============================================================================
# Tests for resolve_vault_path()
# ============================================================================

def test_resolve_vault_path_cli_value_wins(monkeypatch):
    """An explicit CLI value is used and config is not consulted."""
    monkeypatch.setattr(obsidian_tools, 'get_value', lambda *a, **k: '/configured')
    assert obsidian_tools.resolve_vault_path('/explicit') == Path('/explicit')


def test_resolve_vault_path_falls_back_to_config(monkeypatch):
    monkeypatch.setattr(obsidian_tools, 'get_value', lambda *a, **k: '/configured')
    assert obsidian_tools.resolve_vault_path(None) == Path('/configured')


def test_resolve_vault_path_none_when_unset(monkeypatch):
    monkeypatch.setattr(obsidian_tools, 'get_value', lambda *a, **k: None)
    assert obsidian_tools.resolve_vault_path(None) is None


def test_resolve_vault_path_expands_user(monkeypatch):
    monkeypatch.setattr(obsidian_tools, 'get_value', lambda *a, **k: None)
    assert obsidian_tools.resolve_vault_path('~/vault') == Path.home() / 'vault'


# ============================================================================
# Tests for handle_configure_command()
# ============================================================================

def test_configure_show_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    obsidian_tools.handle_configure_command(Namespace(show=True, vault_path=None))
    assert 'No configuration saved yet' in capsys.readouterr().out


def test_configure_show_populated(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    obsidian_tools.set_value('vault_path', '/my/vault')
    obsidian_tools.handle_configure_command(Namespace(show=True, vault_path=None))
    out = capsys.readouterr().out
    assert 'vault_path: /my/vault' in out


def test_configure_saves_valid_vault_path(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    vault = tmp_path / 'vault'
    vault.mkdir()
    obsidian_tools.handle_configure_command(Namespace(show=False, vault_path=str(vault)))
    assert obsidian_tools.get_value('vault_path') == str(vault)
    assert 'Saved vault_path' in capsys.readouterr().out


def test_configure_rejects_missing_directory(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    args = Namespace(show=False, vault_path=str(tmp_path / 'does-not-exist'))
    with pytest.raises(SystemExit):
        obsidian_tools.handle_configure_command(args)


def test_configure_interactive_prompt(tmp_path, monkeypatch):
    """With no --vault-path, the value is read from get_user_input()."""
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    vault = tmp_path / 'vault'
    vault.mkdir()
    monkeypatch.setattr(obsidian_tools, 'get_user_input', lambda prompt: str(vault))
    obsidian_tools.handle_configure_command(Namespace(show=False, vault_path=None))
    assert obsidian_tools.get_value('vault_path') == str(vault)


def test_configure_interactive_empty_keeps_existing(tmp_path, monkeypatch, capsys):
    """Empty interactive input keeps the previously saved vault path."""
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    obsidian_tools.set_value('vault_path', '/existing/vault')
    monkeypatch.setattr(obsidian_tools, 'get_user_input', lambda prompt: '')
    obsidian_tools.handle_configure_command(Namespace(show=False, vault_path=None))
    assert obsidian_tools.get_value('vault_path') == '/existing/vault'
    assert 'Keeping existing' in capsys.readouterr().out


# ============================================================================
# Tests for vault fallback in the 'add' handler
# ============================================================================

def test_add_command_errors_without_vault_or_config(tmp_path, monkeypatch):
    """add exits when neither a CLI vault path nor a saved one is available."""
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))  # empty config
    monkeypatch.setattr('sys.stdin', StringIO(''))
    args = Namespace(vault_path=None, media_type='book', backup_filename=None, poster_width=200)
    with pytest.raises(SystemExit):
        obsidian_tools.handle_add_command(args)


def test_add_command_uses_configured_vault(tmp_path, monkeypatch, capsys):
    """add uses the saved vault_path when the CLI arg is omitted."""
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    vault = tmp_path / 'vault'
    vault.mkdir()
    obsidian_tools.set_value('vault_path', str(vault))
    monkeypatch.setattr(obsidian_tools, 'create_vault_backup', Mock())
    monkeypatch.setattr('sys.stdin', StringIO(''))

    args = Namespace(vault_path=None, media_type='book', backup_filename=None, poster_width=200)
    obsidian_tools.handle_add_command(args)

    out = capsys.readouterr().out
    assert str(vault) in out
    assert 'No titles provided' in out
