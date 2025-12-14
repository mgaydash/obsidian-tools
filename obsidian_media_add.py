#!/usr/bin/env python3
"""
Obsidian Media Note Manager
Add new media notes (movies, TV shows, games) to an Obsidian vault from stdin.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Set

from lib.backup import create_vault_backup
from lib.api import MediaAPIFactory
from lib.poster_downloader import PosterDownloader
from lib.obsidian_utils import extract_title_and_year, filter_results_by_year, find_exact_title_match


def read_titles_from_stdin() -> list[str]:
    """
    Read titles from stdin, one per line.

    Returns:
        List of unique, non-empty titles
    """
    print("📝 Enter titles (one per line), then press Ctrl+D when done:")
    print("-" * 80)

    titles = []
    try:
        for line in sys.stdin:
            title = line.strip()
            if title:  # Skip empty lines
                titles.append(title)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)

    # Remove duplicates while preserving order
    seen: Set[str] = set()
    unique_titles = []
    for title in titles:
        if title not in seen:
            seen.add(title)
            unique_titles.append(title)

    return unique_titles


def process_title(client, vault_path: Path, title_input: str, media_type: str) -> bool:
    """
    Process a single title: search, disambiguate, fetch details, create file.

    Args:
        client: MediaAPIClient instance
        vault_path: Path to Obsidian vault
        title_input: Title to search for (may include year in parentheses)
        media_type: Type of media ('movie', 'tv', or 'game')

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
        overwrite = input("Overwrite? (y/n): ").strip().lower()
        if overwrite != 'y':
            print("⊘ Skipped")
            return False

    # Write the file
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ Successfully created: {filename}")
        return True
    except Exception as e:
        print(f"❌ Error writing file: {e}")
        return False


def handle_add_command(args):
    """Handle the 'add' subcommand."""
    vault_path = Path(args.vault_path)

    # Validate vault path
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
        print("  export IGDB_ACCESS_TOKEN='your_access_token'")
        sys.exit(1)

    # Print header
    media_emoji = {'movie': '🎬', 'tv': '📺', 'game': '🎮'}
    print(f"{media_emoji.get(args.media_type, '📝')} Obsidian Media Note Manager - Add {args.media_type.title()}s")
    print("=" * 80)
    print(f"Vault: {vault_path}")
    print(f"Backup: {args.backup_filename}")
    print(f"Media Type: {args.media_type}")
    print("=" * 80)

    # Create backup
    create_vault_backup(vault_path, args.backup_filename)

    # Read titles from stdin
    titles = read_titles_from_stdin()

    if not titles:
        print("\n✓ No titles provided")
        return

    print(f"\n📋 Found {len(titles)} title(s) to process")
    print("=" * 80)

    # Process each title
    created_count = 0
    skipped_count = 0
    error_count = 0

    for title in titles:
        success = process_title(client, vault_path, title, args.media_type)
        if success:
            created_count += 1
        else:
            # Could be user skip or error
            # We already printed the specific message in process_title
            if "Skipped" in sys.stdout:
                skipped_count += 1
            else:
                error_count += 1

    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"✓ Created: {created_count}")
    print(f"⊘ Skipped: {skipped_count}")
    if error_count > 0:
        print(f"❌ Errors: {error_count}")
    print(f"📦 Backup: {args.backup_filename}")
    print("\n✅ Done!")


def handle_posters_command(args):
    """Handle the 'posters' subcommand."""
    vault_path = Path(args.vault_path)

    # Validate vault path
    if not vault_path.is_dir():
        print(f"❌ Vault path does not exist: {vault_path}")
        sys.exit(1)

    # Get TMDB API key
    tmdb_api_key = os.environ.get('TMDB_API_KEY')
    if not tmdb_api_key:
        print("❌ TMDB_API_KEY environment variable not set")
        print("\nTo get an API key:")
        print("1. Create a free account at https://www.themoviedb.org/")
        print("2. Go to Settings > API and request an API key")
        print("3. Set the environment variable: export TMDB_API_KEY='your_key_here'")
        sys.exit(1)

    # Print header
    print("🖼️  Obsidian Media Note Manager - Download Posters")
    print("=" * 80)
    print(f"Vault: {vault_path}")
    print(f"Backup: {args.backup_filename}")
    print(f"Poster width: {args.width}px")
    print("=" * 80)

    # Create poster downloader
    downloader = PosterDownloader(vault_path, tmdb_api_key, args.width)

    # Create backup
    create_vault_backup(vault_path, args.backup_filename)

    # Find media files
    print("\n🔍 Scanning for movie and series files...")
    print("-" * 80)
    media_files = downloader.find_media_files()

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
    print(f"📦 Backup: {args.backup_filename}")
    print("\n✅ Done!")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Obsidian Media Note Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add movies from stdin
  echo -e "Inception\\nThe Matrix" | python obsidian_media_add.py add ~/vault backup.zip --media-type movie

  # Add TV shows interactively
  python obsidian_media_add.py add ~/vault backup.zip --media-type tv

  # Add games
  echo -e "Elden Ring\\nHollow Knight" | python obsidian_media_add.py add ~/vault backup.zip --media-type game

  # Download posters for existing notes
  python obsidian_media_add.py posters ~/vault backup.zip

  # Download posters at custom width
  python obsidian_media_add.py posters ~/vault backup.zip --width 300

Environment Variables:
  TMDB_API_KEY          Required for movies and TV shows
  IGDB_CLIENT_ID        Required for games (Twitch application client ID)
  IGDB_ACCESS_TOKEN     Required for games (Twitch OAuth access token)
        """
    )

    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

    # 'add' subcommand
    add_parser = subparsers.add_parser(
        'add',
        help='Add new media notes from stdin',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    add_parser.add_argument('vault_path', help='Path to Obsidian vault')
    add_parser.add_argument('backup_filename', help='Backup filename (e.g., backup.zip)')
    add_parser.add_argument(
        '--media-type',
        required=True,
        choices=['movie', 'tv', 'game'],
        help='Type of media to add'
    )

    # 'posters' subcommand
    posters_parser = subparsers.add_parser(
        'posters',
        help='Download posters for existing movie and series notes',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    posters_parser.add_argument('vault_path', help='Path to Obsidian vault')
    posters_parser.add_argument('backup_filename', help='Backup filename (e.g., backup.zip)')
    posters_parser.add_argument(
        '--width',
        type=int,
        default=200,
        help='Poster width in pixels (default: 200, range: 50-2000)'
    )

    # Parse arguments
    args = parser.parse_args()

    # Validate width for posters command
    if args.command == 'posters':
        if args.width < 50 or args.width > 2000:
            print("❌ Width must be between 50 and 2000 pixels")
            sys.exit(1)

    # Route to appropriate handler
    if args.command == 'add':
        handle_add_command(args)
    elif args.command == 'posters':
        handle_posters_command(args)


if __name__ == "__main__":
    main()
