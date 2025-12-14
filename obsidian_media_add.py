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


def process_title(client, vault_path: Path, title: str) -> bool:
    """
    Process a single title: search, disambiguate, fetch details, create file.

    Args:
        client: MediaAPIClient instance
        vault_path: Path to Obsidian vault
        title: Title to search for

    Returns:
        True if successful, False if skipped or failed
    """
    print(f"\n{'='*80}")
    print(f"Processing: {title}")
    print(f"{'='*80}")

    # Search for the title
    try:
        results = client.search(title)
    except Exception as e:
        print(f"❌ Error searching: {e}")
        return False

    if not results:
        print(f"❌ No results found for '{title}'")
        return False

    # Handle disambiguation
    if len(results) > 1:
        selected = client.prompt_disambiguation(title, results)
        if selected is None:
            print("⊘ Skipped by user")
            return False
    else:
        selected = results[0]

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
        success = process_title(client, vault_path, title)
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

    # Parse arguments
    args = parser.parse_args()

    # Route to appropriate handler
    if args.command == 'add':
        handle_add_command(args)


if __name__ == "__main__":
    main()
