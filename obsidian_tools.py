#!/usr/bin/env python3
"""
Obsidian Tools - Media Note Manager
Add new media notes (movies, TV shows, games, albums, books) to an Obsidian vault from stdin.
"""

import os
import sys
import argparse
import yaml
import time
from pathlib import Path
from typing import Optional, Set

from lib.backup import create_vault_backup
from lib.api import MediaAPIFactory
from lib.poster_downloader import PosterDownloader
from lib.config import get_config_path, get_value, load_config, set_value
from lib.obsidian_utils import (
    extract_title_and_year,
    filter_results_by_year,
    find_exact_title_match,
    get_user_input,
    is_game_unreleased,
    prompt_unreleased_confirmation
)
from lib.poster_utils import download_and_resize_poster, update_frontmatter_with_poster, extract_yaml_frontmatter


def resolve_vault_path(cli_value: Optional[str]) -> Optional[Path]:
    """Resolve the vault path from the CLI arg, falling back to saved config.

    Returns an expanded Path, or None if neither a CLI value nor a configured
    vault_path is available.
    """
    value = cli_value or get_value('vault_path')
    return Path(value).expanduser() if value else None


def normalize_titles(titles: list[str]) -> list[str]:
    """
    Strip whitespace, drop empty entries, and de-duplicate while preserving order.

    Shared by the stdin reader and the command-line title arguments so both
    inputs behave identically.
    """
    seen: Set[str] = set()
    unique_titles = []
    for title in titles:
        title = title.strip()
        if title and title not in seen:  # Skip empty lines and duplicates
            seen.add(title)
            unique_titles.append(title)

    return unique_titles


def read_titles_from_stdin() -> list[str]:
    """
    Read titles from stdin, one per line.

    Returns:
        List of unique, non-empty titles
    """
    print("📝 Enter titles (one per line), then press Ctrl+D when done:")
    print("-" * 80)

    lines = []
    try:
        for line in sys.stdin:
            lines.append(line)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)

    return normalize_titles(lines)


def embed_poster_in_content(file_path: Path, poster_filename: str) -> bool:
    """
    Embed poster image at the beginning of the file content.

    Args:
        file_path: Path to markdown file
        poster_filename: Name of poster file (e.g., 'Movie (2020).jpg')

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        frontmatter, remaining = extract_yaml_frontmatter(content)

        if not frontmatter:
            return False

        # Build new content with embed
        # Format: ---\n{yaml}---\n\n![[poster.jpg]]\n\n{original content}
        yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)

        # Remove leading newlines from remaining to avoid extra spacing
        remaining_stripped = remaining.lstrip('\n')

        new_content = f"---\n{yaml_str}---\n\n![[{poster_filename}]]\n\n{remaining_stripped}"

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return True

    except Exception as e:
        print(f"❌ Error embedding poster: {e}")
        return False


def process_title(
    client,
    vault_path: Path,
    title_input: str,
    media_type: str,
    poster_width: int = 200
) -> bool:
    """
    Process a single title: search, disambiguate, fetch details, create file, download poster.

    Args:
        client: MediaAPIClient instance
        vault_path: Path to Obsidian vault
        title_input: Title to search for (may include year in parentheses)
        media_type: Type of media ('movie', 'tv', 'game', 'album', or 'book')
        poster_width: Width to resize posters to (default: 200px)

    Returns:
        True if successful, False if skipped or failed
    """
    print(f"\n{'='*80}")
    print(f"Processing: {title_input}")
    print(f"{'='*80}")

    # Extract title and year from input
    title, year = extract_title_and_year(title_input)

    if year:
        print(f"📅 Detected year: {year} - will use for auto-disambiguation")

    # Search for the title (without year)
    try:
        results = client.search(title)
    except Exception as e:
        print(f"❌ Error searching: {e}")
        return False

    if not results:
        print(f"❌ No results found for '{title}'")
        return False

    # Filter by year if provided
    if year:
        year_filtered = filter_results_by_year(results, year, media_type)
        if year_filtered:
            results = year_filtered
            print(f"✓ Filtered to {len(results)} result(s) matching year {year}")
        else:
            print(f"⚠️  No results found for year {year}, showing all results")

    # Check for exact title match
    exact_match = find_exact_title_match(results, title, media_type)
    if exact_match:
        # For games, check if unreleased and prompt for confirmation
        if media_type == 'game' and is_game_unreleased(exact_match):
            game_title = exact_match.get('name', title)
            if not prompt_unreleased_confirmation(game_title):
                print("⊘ Skipped by user")
                return False
        print(f"✓ Auto-selected exact title match")
        selected = exact_match
    # Handle disambiguation
    elif len(results) > 1:
        selected = client.prompt_disambiguation(title, results)
        if selected is None:
            print("⊘ Skipped by user")
            return False
    else:
        selected = results[0]
        if year:
            print(f"✓ Auto-selected the only result matching year {year}")

    # Get detailed information
    media_id = str(selected.get('id'))
    try:
        details = client.get_details(media_id)
    except Exception as e:
        print(f"❌ Error fetching details: {e}")
        return False

    # Generate filename and content
    try:
        filename = client.get_filename(details)
        content = client.format_note_content(details)
    except Exception as e:
        print(f"❌ Error generating content: {e}")
        return False

    # Check if file already exists
    file_path = vault_path / filename
    if file_path.exists():
        print(f"⚠️  File already exists: {filename}")
        overwrite = get_user_input("Overwrite? (y/n): ").strip().lower()
        if overwrite != 'y':
            print("⊘ Skipped")
            return False

    # Write the file
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ Successfully created: {filename}")
    except Exception as e:
        print(f"❌ Error writing file: {e}")
        return False

    # Download poster for all media types
    poster_url = client.get_poster_url(details)
    if poster_url:
        print(f"📥 Downloading poster...")
        poster_filename = file_path.stem + '.jpg'
        poster_file_path = file_path.parent / poster_filename

        if download_and_resize_poster(poster_url, poster_file_path, poster_width):
            print(f"✓ Poster saved: {poster_filename}")
            if update_frontmatter_with_poster(file_path, poster_filename):
                print(f"✓ Frontmatter updated with poster wikilink")
                # Embed the poster at the beginning of the content
                if embed_poster_in_content(file_path, poster_filename):
                    print(f"✓ Poster embedded in content")
                else:
                    print(f"⚠️  Failed to embed poster in content")
            else:
                print(f"⚠️  Failed to update frontmatter with poster")
        else:
            print(f"⚠️  Failed to download poster")
    else:
        print(f"⚠️  No poster available for this {media_type}")

    return True


def handle_add_command(args):
    """Handle the 'add' subcommand."""
    vault_path = resolve_vault_path(args.vault_path)

    # Validate vault path
    if vault_path is None:
        print("❌ No vault path provided. Pass one as an argument or save one with:")
        print("     obsidian-tools configure --vault-path <path>")
        sys.exit(1)
    if not vault_path.is_dir():
        print(f"❌ Vault path does not exist: {vault_path}")
        sys.exit(1)

    # Create API client
    try:
        client = MediaAPIFactory.create_client(args.media_type)
    except ValueError as e:
        print(f"❌ {e}")
        print("\nFor TMDB (movies/TV):")
        print("  export TMDB_API_KEY='your_key_here'")
        print("\nFor IGDB (games):")
        print("  export IGDB_CLIENT_ID='your_client_id'")
        print("  export IGDB_CLIENT_SECRET='your_client_secret'")
        print("\nFor MusicBrainz (albums):")
        print("  No credentials needed!")
        print("\nFor Open Library (books):")
        print("  No credentials needed!")
        sys.exit(1)

    # Print header
    media_emoji = {'movie': '🎬', 'tv': '📺', 'game': '🎮', 'album': '🎵', 'book': '📚'}
    print(f"{media_emoji.get(args.media_type, '📝')} Obsidian Media Note Manager - Add {args.media_type.title()}s")
    print("=" * 80)
    print(f"Vault: {vault_path}")
    print(f"Backup: {args.backup_filename if args.backup_filename else 'disabled'}")
    print(f"Media Type: {args.media_type}")
    print(f"Poster width: {args.poster_width}px")
    print("=" * 80)

    # Create backup (only when requested via -b/--backup)
    if args.backup_filename:
        create_vault_backup(vault_path, args.backup_filename)

    # Use titles passed as command-line arguments, otherwise read from stdin
    if args.titles:
        titles = normalize_titles(args.titles)
    else:
        titles = read_titles_from_stdin()

    if not titles:
        print("\n✓ No titles provided")
        return

    print(f"\n📋 Found {len(titles)} title(s) to process")
    print("=" * 80)

    # Process each title
    created_count = 0
    failed_count = 0

    for title in titles:
        success = process_title(
            client,
            vault_path,
            title,
            args.media_type,
            args.poster_width
        )
        if success:
            created_count += 1
        else:
            failed_count += 1

        # Rate limiting for MusicBrainz API (max 1 request/second)
        if args.media_type == 'album':
            time.sleep(1.1)
        # Be polite to Open Library: small pause between books
        elif args.media_type == 'book':
            time.sleep(0.5)

    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"✓ Created: {created_count}")
    print(f"⊘ Skipped/Failed: {failed_count}")
    if args.backup_filename:
        print(f"📦 Backup: {args.backup_filename}")
    print("\n✅ Done!")


def handle_posters_command(args):
    """Handle the 'posters' subcommand."""
    vault_path = resolve_vault_path(args.vault_path)

    # Validate vault path
    if vault_path is None:
        print("❌ No vault path provided. Pass one as an argument or save one with:")
        print("     obsidian-tools configure --vault-path <path>")
        sys.exit(1)
    if not vault_path.is_dir():
        print(f"❌ Vault path does not exist: {vault_path}")
        sys.exit(1)

    # Get API credentials
    tmdb_api_key = os.environ.get('TMDB_API_KEY')
    igdb_client_id = os.environ.get('IGDB_CLIENT_ID')
    igdb_client_secret = os.environ.get('IGDB_CLIENT_SECRET')

    # Print header
    print("🖼️  Obsidian Media Note Manager - Download Posters")
    print("=" * 80)
    print(f"Vault: {vault_path}")
    print(f"Backup: {args.backup_filename if args.backup_filename else 'disabled'}")
    print(f"Media type filter: {args.media_type}")
    print(f"Poster width: {args.width}px")
    print("=" * 80)

    # Create poster downloader
    downloader = PosterDownloader(
        vault_path,
        tmdb_api_key=tmdb_api_key,
        igdb_client_id=igdb_client_id,
        igdb_client_secret=igdb_client_secret,
        poster_width=args.width
    )

    # Create backup (only when requested via -b/--backup)
    if args.backup_filename:
        create_vault_backup(vault_path, args.backup_filename)

    # Find media files
    print("\n🔍 Scanning for media files...")
    print("-" * 80)
    media_files = downloader.find_media_files()

    # Apply media type filter
    if args.media_type != 'all':
        # Convert 'tv' CLI arg to 'series' for internal consistency
        filter_type = 'series' if args.media_type == 'tv' else args.media_type
        media_files = [(f, t) for f, t in media_files if t == filter_type]
        print(f"✓ Filtered to {args.media_type} files only")

    if not media_files:
        print("\n✓ No files found that need poster processing")
        return

    print(f"\n📋 Found {len(media_files)} file(s) to process")
    print("=" * 80)

    # Process each file
    processed_count = 0
    skipped_count = 0

    for file_path, media_type in media_files:
        success = downloader.process_file(file_path, media_type)
        if success:
            processed_count += 1
        else:
            skipped_count += 1

    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"✓ Processed: {processed_count}")
    print(f"⊘ Skipped: {skipped_count}")
    if args.backup_filename:
        print(f"📦 Backup: {args.backup_filename}")
    print("\n✅ Done!")


def handle_configure_command(args):
    """Handle the 'configure' subcommand: save persistent settings."""
    config_path = get_config_path()

    # --show: print the current configuration and exit
    if args.show:
        config = load_config()
        if not config:
            print(f"No configuration saved yet ({config_path})")
            return
        print(f"Configuration ({config_path}):")
        for key in sorted(config):
            print(f"  {key}: {config[key]}")
        return

    # Determine the vault path: from --vault-path or an interactive prompt
    vault_path = args.vault_path
    if vault_path is None:
        current = load_config().get('vault_path')
        prompt = f"Vault path [{current}]: " if current else "Vault path: "
        try:
            entered = get_user_input(prompt).strip()
        except EOFError:
            print("❌ No input received")
            sys.exit(1)
        if not entered:
            if current:
                print("✓ Keeping existing vault path")
                return
            print("❌ No vault path provided")
            sys.exit(1)
        vault_path = entered

    # Validate before persisting
    expanded = Path(vault_path).expanduser()
    if not expanded.is_dir():
        print(f"❌ Vault path does not exist or is not a directory: {expanded}")
        sys.exit(1)

    saved_path = set_value('vault_path', str(expanded))
    print(f"✓ Saved vault_path to {saved_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Obsidian Media Note Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Save a default vault path once, then omit it in later commands
  python obsidian_tools.py configure --vault-path ~/vault
  python obsidian_tools.py configure --show

  # Add movies by passing titles as arguments (uses the configured vault path)
  python obsidian_tools.py add movie "Inception" "The Matrix (1999)"

  # Add movies from stdin (used when no title arguments are given)
  echo -e "Inception\\nThe Matrix" | python obsidian_tools.py add movie

  # Add TV shows interactively, to an explicit vault (overrides the saved one)
  python obsidian_tools.py add tv --vault-path ~/other-vault

  # Add games, backing up the vault first
  echo -e "Elden Ring\\nHollow Knight" | python obsidian_tools.py add game -b backup.zip

  # Add albums
  echo "Dark Side of the Moon (1973)" | python obsidian_tools.py add album

  # Add books
  echo -e "Dune\nThe Hobbit (1937)" | python obsidian_tools.py add book

  # Download posters for existing notes (all media types)
  python obsidian_tools.py posters

  # Download posters at custom width, for an explicit vault
  python obsidian_tools.py posters --width 300 --vault-path ~/vault

  # Download posters, backing up the vault first
  python obsidian_tools.py posters --media-type album -b backup.zip

Environment Variables:
  TMDB_API_KEY          Required for movies and TV shows
  IGDB_CLIENT_ID        Required for games (Twitch application client ID)
  IGDB_CLIENT_SECRET    Required for games (Twitch application client secret)
  MusicBrainz (albums)  No credentials needed!
  Open Library (books)  No credentials needed!
        """
    )

    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

    # 'add' subcommand
    add_parser = subparsers.add_parser(
        'add',
        help='Add new media notes from stdin',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    add_parser.add_argument(
        'media_type',
        choices=['movie', 'tv', 'game', 'album', 'book'],
        help='Type of media to add'
    )
    add_parser.add_argument(
        'titles',
        nargs='*',
        metavar='TITLE',
        help='One or more titles to add (e.g., "Dune" "The Matrix (1999)"). '
             'If omitted, titles are read from stdin, one per line.'
    )
    add_parser.add_argument(
        '--vault-path',
        dest='vault_path',
        metavar='PATH',
        default=None,
        help='Path to Obsidian vault (defaults to the configured vault_path; '
             'set one with "configure --vault-path")'
    )
    add_parser.add_argument(
        '-b', '--backup',
        dest='backup_filename',
        metavar='FILE',
        default=None,
        help='Back up the vault to FILE (e.g., backup.zip) before adding notes. '
             'Backup is skipped when omitted.'
    )
    add_parser.add_argument(
        '--poster-width',
        type=int,
        default=200,
        help='Poster width in pixels for movies/TV (default: 200, range: 50-2000)'
    )

    # 'posters' subcommand
    posters_parser = subparsers.add_parser(
        'posters',
        help='Download posters for existing movie and series notes',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    posters_parser.add_argument(
        '--vault-path',
        dest='vault_path',
        metavar='PATH',
        default=None,
        help='Path to Obsidian vault (defaults to the configured vault_path; '
             'set one with "configure --vault-path")'
    )
    posters_parser.add_argument(
        '-b', '--backup',
        dest='backup_filename',
        metavar='FILE',
        default=None,
        help='Back up the vault to FILE (e.g., backup.zip) before downloading posters. '
             'Backup is skipped when omitted.'
    )
    posters_parser.add_argument(
        '--width',
        type=int,
        default=200,
        help='Poster width in pixels (default: 200, range: 50-2000)'
    )
    posters_parser.add_argument(
        '--media-type',
        choices=['all', 'movie', 'tv', 'game', 'album', 'book'],
        default='all',
        help='Filter by media type (default: all)'
    )

    # 'configure' subcommand
    configure_parser = subparsers.add_parser(
        'configure',
        help='Save persistent settings (e.g., the default vault path)',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    configure_parser.add_argument(
        '--vault-path',
        dest='vault_path',
        default=None,
        help='Vault path to save as the default; prompts interactively if omitted'
    )
    configure_parser.add_argument(
        '--show',
        action='store_true',
        help='Print the saved configuration and exit'
    )

    # Parse arguments
    args = parser.parse_args()

    # Validate width arguments
    if args.command == 'posters':
        if args.width < 50 or args.width > 2000:
            print("❌ Width must be between 50 and 2000 pixels")
            sys.exit(1)
    elif args.command == 'add':
        if args.poster_width < 50 or args.poster_width > 2000:
            print("❌ Poster width must be between 50 and 2000 pixels")
            sys.exit(1)

    # Route to appropriate handler
    if args.command == 'add':
        handle_add_command(args)
    elif args.command == 'posters':
        handle_posters_command(args)
    elif args.command == 'configure':
        handle_configure_command(args)


if __name__ == "__main__":
    main()
