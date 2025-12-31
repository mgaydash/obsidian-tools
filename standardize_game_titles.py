#!/usr/bin/env python3
"""
Obsidian Tools - Standardize Game Note Titles

Standardizes all game notes to "Name (Year).md" format by fetching release
years from IGDB. Handles various existing formats and updates all references.
"""

import os
import sys
import re
import argparse
import yaml
from pathlib import Path
from typing import List, Optional, Tuple, Dict

from lib.backup import create_vault_backup
from lib.api.igdb_client import IGDBClient
from lib.obsidian_utils import (
    extract_title_and_year,
    filter_results_by_year,
    find_exact_title_match,
    sanitize_filename,
    get_user_input
)
from lib.poster_utils import extract_yaml_frontmatter


def parse_game_filename(filename: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Parse game filename and extract title, year, platform.

    Args:
        filename: Filename without .md extension

    Returns:
        Tuple of (title, year, platform)
        - year is None if not found or if parenthetical is a platform
        - platform is None if not found or if parenthetical is a year
    """
    # Known gaming platforms
    PLATFORMS = {
        'ipad', 'iphone', 'ios', 'pc', 'mac', 'linux', 'steam',
        'playstation', 'ps4', 'ps5', 'xbox', 'switch', 'nintendo',
        'mobile', 'android', 'windows', 'macos'
    }

    # Try to extract (XXXX) pattern
    match = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', filename)

    if match:
        title, parenthetical = match.groups()
        title = title.strip()
        parenthetical = parenthetical.strip()

        # Check if it's a 4-digit year
        if re.match(r'^\d{4}$', parenthetical):
            return title, parenthetical, None

        # Check if it's a known platform (case-insensitive)
        if parenthetical.lower() in PLATFORMS:
            return title, None, parenthetical

        # Unknown parenthetical - could be edition name, etc.
        # Keep it as part of title for now
        return filename, None, None

    # No parentheses - just the title
    return filename, None, None


class GameTitleStandardizer:
    """Standardize game note titles to 'Name (Year).md' format."""

    def __init__(self, vault_path: Path, dry_run: bool = False):
        """
        Initialize the standardizer.

        Args:
            vault_path: Path to Obsidian vault
            dry_run: If True, preview changes without applying them
        """
        self.vault_path = vault_path
        self.dry_run = dry_run
        self.changes = []  # Track all changes for summary

        # Initialize IGDB client
        client_id = os.environ.get('IGDB_CLIENT_ID')
        client_secret = os.environ.get('IGDB_CLIENT_SECRET')
        if not client_id or not client_secret:
            raise ValueError("IGDB credentials not found in environment")

        self.igdb_client = IGDBClient(client_id, client_secret)

    def find_game_notes(self) -> List[Path]:
        """
        Find all game notes in the vault.

        Returns:
            List of Path objects to game note files
        """
        game_notes = []

        for md_file in self.vault_path.rglob('*.md'):
            # Skip Templates folder
            if 'Templates' in md_file.parts:
                continue

            # Skip backup files
            if '.backup.' in md_file.name:
                continue

            # Check if file has 'game' tag
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                frontmatter, _ = extract_yaml_frontmatter(content)
                if frontmatter and 'tags' in frontmatter:
                    tags = frontmatter['tags']
                    if isinstance(tags, list):
                        tags_lower = [str(t).lower() for t in tags]
                        if 'game' in tags_lower:
                            game_notes.append(md_file)
            except Exception as e:
                print(f"⚠️  Error reading {md_file.name}: {e}")
                continue

        return game_notes

    def get_correct_filename(
        self,
        file_path: Path,
        current_title: str,
        current_year: Optional[str]
    ) -> Optional[str]:
        """
        Look up game on IGDB and return correct filename.

        Args:
            file_path: Current file path
            current_title: Extracted title from current filename
            current_year: Extracted year (if any) from current filename

        Returns:
            Correct filename (without .md) or None if should skip
        """
        print(f"\n{'='*80}")
        print(f"Processing: {file_path.name}")
        print(f"{'='*80}")
        print(f"Current title: {current_title}")
        if current_year:
            print(f"Current year: {current_year}")

        # Search IGDB
        try:
            results = self.igdb_client.search(current_title)
        except Exception as e:
            print(f"❌ Error searching IGDB: {e}")
            return None

        if not results:
            print(f"❌ No results found for '{current_title}'")
            return None

        # Filter by year if we have one
        if current_year:
            year_filtered = filter_results_by_year(results, current_year, 'game')
            if year_filtered:
                results = year_filtered
                print(f"✓ Filtered to {len(results)} result(s) matching year {current_year}")

        # Check for exact title match
        exact_match = find_exact_title_match(results, current_title, 'game')
        if exact_match:
            print(f"✓ Auto-selected exact title match")
            selected = exact_match
        # Disambiguation
        elif len(results) > 1:
            selected = self.igdb_client.prompt_disambiguation(current_title, results)
            if selected is None:
                print("⊘ Skipped by user")
                return None
        else:
            selected = results[0]
            print(f"✓ Auto-selected single result")

        # Get correct filename
        details = self.igdb_client.get_details(str(selected['id']))
        correct_filename = self.igdb_client.get_filename(details).replace('.md', '')

        return correct_filename

    def update_wikilinks_in_vault(self, old_name: str, new_name: str) -> int:
        """
        Update all wikilinks referencing the old filename.

        Args:
            old_name: Old filename (without .md)
            new_name: New filename (without .md)

        Returns:
            Number of files updated
        """
        files_updated = 0

        # Patterns to match
        # [[Old Name]] -> [[New Name]]
        # [[Old Name|alias]] -> [[New Name|alias]]
        simple_pattern = re.compile(r'\[\[' + re.escape(old_name) + r'\]\]')
        aliased_pattern = re.compile(r'\[\[' + re.escape(old_name) + r'\|([^\]]+)\]\]')

        for md_file in self.vault_path.rglob('*.md'):
            if 'Templates' in md_file.parts or '.backup.' in md_file.name:
                continue

            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check if file contains references
                if old_name not in content:
                    continue

                original_content = content

                # Replace simple wikilinks
                content = simple_pattern.sub(f'[[{new_name}]]', content)

                # Replace aliased wikilinks
                content = aliased_pattern.sub(rf'[[{new_name}|\1]]', content)

                # Write back if changed
                if content != original_content:
                    if not self.dry_run:
                        with open(md_file, 'w', encoding='utf-8') as f:
                            f.write(content)
                    files_updated += 1
                    print(f"  ✓ Updated wikilinks in: {md_file.name}")

            except Exception as e:
                print(f"  ⚠️  Error updating {md_file.name}: {e}")

        return files_updated

    def update_poster_frontmatter(self, file_path: Path, poster_filename: str):
        """
        Update poster reference in frontmatter.

        Args:
            file_path: Path to markdown file
            poster_filename: Name of poster file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            frontmatter, remaining = extract_yaml_frontmatter(content)
            if frontmatter:
                frontmatter['poster'] = f"[[{poster_filename}]]"

                yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
                new_content = f"---\n{yaml_str}---{remaining}"

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
        except Exception as e:
            print(f"  ⚠️  Error updating poster frontmatter: {e}")

    def rename_poster_if_exists(self, old_path: Path, new_path: Path) -> bool:
        """
        Rename associated poster file if it exists.

        Args:
            old_path: Current .md file path
            new_path: New .md file path

        Returns:
            True if poster was renamed, False otherwise
        """
        old_poster = old_path.with_suffix('.jpg')
        new_poster = new_path.with_suffix('.jpg')

        if old_poster.exists():
            if not self.dry_run:
                old_poster.rename(new_poster)
            print(f"  ✓ Renamed poster: {old_poster.name} → {new_poster.name}")

            # Update frontmatter poster reference
            if not self.dry_run:
                self.update_poster_frontmatter(new_path, new_poster.name)

            return True

        return False

    def process_game_note(self, file_path: Path) -> bool:
        """
        Process a single game note.

        Args:
            file_path: Path to game note file

        Returns:
            True if file was renamed, False otherwise
        """
        # Parse current filename
        current_name = file_path.stem  # Remove .md
        title, year, platform = parse_game_filename(current_name)

        # Get correct filename from IGDB
        correct_name = self.get_correct_filename(file_path, title, year)

        if correct_name is None:
            return False

        # Check if rename needed
        if current_name == correct_name:
            print(f"✓ Already correct: {correct_name}.md")
            return False

        # Show change
        new_path = file_path.parent / f"{correct_name}.md"
        print(f"\n📝 Change:")
        print(f"  Old: {current_name}.md")
        print(f"  New: {correct_name}.md")

        if self.dry_run:
            print(f"  [DRY RUN] Would rename file")
        else:
            # Rename file
            file_path.rename(new_path)
            print(f"  ✓ Renamed file")

        # Rename poster if exists
        poster_renamed = self.rename_poster_if_exists(file_path, new_path)

        # Update wikilinks
        print(f"\n🔗 Updating wikilinks...")
        wikilink_count = self.update_wikilinks_in_vault(current_name, correct_name)
        if wikilink_count > 0:
            print(f"  ✓ Updated {wikilink_count} file(s) with wikilinks")
        else:
            print(f"  ✓ No wikilinks to update")

        # Track change
        self.changes.append({
            'old': current_name,
            'new': correct_name,
            'poster_renamed': poster_renamed,
            'wikilinks_updated': wikilink_count
        })

        return True

    def run(self) -> None:
        """Main execution method."""
        print("🎮 Game Title Standardizer")
        print("=" * 80)
        print(f"Vault: {self.vault_path}")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print("=" * 80)

        # Find game notes
        print("\n🔍 Scanning for game notes...")
        game_notes = self.find_game_notes()
        print(f"✓ Found {len(game_notes)} game note(s)")

        if not game_notes:
            print("\n✓ No game notes found")
            return

        # Process each note
        renamed_count = 0
        skipped_count = 0

        for file_path in game_notes:
            if self.process_game_note(file_path):
                renamed_count += 1
            else:
                skipped_count += 1

        # Summary
        print("\n" + "=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        print(f"✓ Renamed: {renamed_count}")
        print(f"⊘ Skipped: {skipped_count}")

        if self.dry_run:
            print("\n💡 This was a dry run. Use without --dry-run to apply changes.")
        else:
            print("\n✅ Done!")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Standardize game note titles to "Name (Year)" format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Dry run to preview changes
  python standardize_game_titles.py ~/vault --dry-run

  # Apply changes with backup
  python standardize_game_titles.py ~/vault backup.zip

Environment variables required:
  IGDB_CLIENT_ID      - IGDB API client ID
  IGDB_CLIENT_SECRET  - IGDB API client secret
        '''
    )

    parser.add_argument('vault_path', help='Path to Obsidian vault')
    parser.add_argument(
        'backup_filename',
        nargs='?',
        default=None,
        help='Backup filename (e.g., backup.zip). Skipped in dry-run mode.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without applying them'
    )

    args = parser.parse_args()

    vault_path = Path(args.vault_path)

    # Validate vault
    if not vault_path.is_dir():
        print(f"❌ Vault path does not exist: {vault_path}")
        sys.exit(1)

    # Check credentials
    if not os.environ.get('IGDB_CLIENT_ID') or not os.environ.get('IGDB_CLIENT_SECRET'):
        print("❌ IGDB credentials not found in environment")
        print("\nSet the following environment variables:")
        print("  export IGDB_CLIENT_ID='your_client_id'")
        print("  export IGDB_CLIENT_SECRET='your_client_secret'")
        sys.exit(1)

    # Create backup (skip in dry-run)
    if not args.dry_run:
        if not args.backup_filename:
            print("❌ Backup filename required when not in dry-run mode")
            sys.exit(1)

        print("\n📦 Creating backup...")
        create_vault_backup(vault_path, args.backup_filename)
        print(f"✓ Backup created: {args.backup_filename}")

    # Run standardizer
    try:
        standardizer = GameTitleStandardizer(vault_path, dry_run=args.dry_run)
        standardizer.run()
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
