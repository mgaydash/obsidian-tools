#!/usr/bin/env python3
"""
Obsidian Game Notes Migration Script

Migrates game notes from tag-based to property-based wikilink system.
Converts player tags to wikilinks and determines status from tags/properties.
"""

import os
import sys
import argparse
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

from lib.backup import create_vault_backup


class ChangeType(Enum):
    """Types of changes made to a note."""
    TAG_REMOVED = "tag_removed"
    TAG_ADDED = "tag_added"
    PROPERTY_ADDED = "property_added"
    PROPERTY_UPDATED = "property_updated"
    NO_CHANGE = "no_change"


@dataclass
class Change:
    """Represents a single change made to a note."""
    change_type: ChangeType
    description: str


@dataclass
class MigrationResult:
    """Result of migrating a single file."""
    file_path: Path
    success: bool
    changes: List[Change]
    error: Optional[str] = None

    @property
    def has_changes(self) -> bool:
        """Check if any actual changes were made."""
        return any(c.change_type != ChangeType.NO_CHANGE for c in self.changes)


class PlayerMapping:
    """Manages player tag to wikilink mappings."""

    def __init__(self):
        # Store list of names for each tag to support multiple players per tag
        self.mappings: Dict[str, List[str]] = {
            'jordan': ['Jordan Godfrey']
        }

    def add_mapping(self, tag: str, names: str):
        """
        Add a player tag to name(s) mapping.

        Args:
            tag: The tag to map from (e.g., 'bob', 'CJK')
            names: Single name or comma-separated names (e.g., 'Bob Smith' or 'Craig,Jon,Billy')
        """
        # Parse comma-separated names
        name_list = [name.strip() for name in names.split(',') if name.strip()]
        self.mappings[tag.lower()] = name_list

    def get_wikilinks(self, tag: str) -> List[str]:
        """
        Get wikilinks for a player tag.

        Returns:
            List of wikilink strings (e.g., ['[[Bob Smith]]', '[[Jane Doe]]'])
        """
        names = self.mappings.get(tag.lower(), [])
        return [f"[[{name}]]" for name in names]

    def is_player_tag(self, tag: str) -> bool:
        """Check if a tag is a player tag."""
        return tag.lower() in self.mappings


class ObsidianNoteMigrator:
    """Handles migration of Obsidian game notes."""

    def __init__(self, vault_path: Path, player_mapping: PlayerMapping, verbose: bool = False):
        self.vault_path = vault_path
        self.player_mapping = player_mapping
        self.verbose = verbose

    def log(self, message: str):
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"  [DEBUG] {message}")

    def extract_frontmatter(self, content: str) -> Tuple[Optional[Dict], str, str]:
        """
        Extract YAML frontmatter from markdown content.

        Returns:
            Tuple of (frontmatter_dict, body_content, original_yaml_string)
        """
        if not content.startswith('---'):
            return None, content, ""

        # Split content by --- delimiters
        parts = content.split('---', 2)
        if len(parts) < 3:
            return None, content, ""

        yaml_string = parts[1]
        body = parts[2]

        try:
            frontmatter = yaml.safe_load(yaml_string)
            if frontmatter is None:
                frontmatter = {}
            return frontmatter, body, yaml_string
        except yaml.YAMLError as e:
            self.log(f"YAML parsing error: {e}")
            return None, content, ""

    def has_game_tag(self, frontmatter: Dict) -> bool:
        """Check if frontmatter has 'game' tag."""
        if not frontmatter or 'tags' not in frontmatter:
            return False

        tags = frontmatter['tags']
        if isinstance(tags, list):
            return 'game' in tags
        elif isinstance(tags, str):
            return tags == 'game'
        return False

    def normalize_tags(self, tags) -> List[str]:
        """Normalize tags to a list format."""
        if tags is None:
            return []
        if isinstance(tags, str):
            return [tags]
        if isinstance(tags, list):
            return [str(t) for t in tags]
        return []

    def migrate_frontmatter(self, frontmatter: Dict) -> Tuple[Dict, List[Change]]:
        """
        Apply migration rules to frontmatter.

        Returns:
            Tuple of (updated_frontmatter, list_of_changes)
        """
        updated = frontmatter.copy()
        changes: List[Change] = []

        # Get current tags
        tags = self.normalize_tags(updated.get('tags', []))
        original_tags = tags.copy()

        # 1. Convert player tags to players property
        player_wikilinks: Set[str] = set()

        # Check existing players property
        if 'players' in updated:
            existing_players = updated['players']
            if isinstance(existing_players, list):
                player_wikilinks.update(existing_players)

        # Find and convert player tags
        tags_to_remove = []
        for tag in tags:
            if self.player_mapping.is_player_tag(tag):
                wikilinks = self.player_mapping.get_wikilinks(tag)
                if wikilinks:
                    player_wikilinks.update(wikilinks)
                    tags_to_remove.append(tag)
                    changes.append(Change(
                        ChangeType.TAG_REMOVED,
                        f"Removed '{tag}' tag"
                    ))

        # Remove player tags from tags list
        for tag in tags_to_remove:
            tags.remove(tag)

        # Add or update players property
        if player_wikilinks:
            player_list = sorted(list(player_wikilinks))
            if 'players' not in updated:
                updated['players'] = player_list
                changes.append(Change(
                    ChangeType.PROPERTY_ADDED,
                    f"Added players: {player_list}"
                ))
            elif updated['players'] != player_list:
                updated['players'] = player_list
                changes.append(Change(
                    ChangeType.PROPERTY_UPDATED,
                    f"Updated players: {player_list}"
                ))

        # 2. Determine and set status
        if 'status' not in updated:
            status = None

            # Check for 'wip' tag
            if 'wip' in tags:
                status = 'playing'
                tags.remove('wip')
                changes.append(Change(
                    ChangeType.TAG_REMOVED,
                    "Removed 'wip' tag"
                ))
                changes.append(Change(
                    ChangeType.PROPERTY_ADDED,
                    "Added status: playing"
                ))
            # Check for rating
            elif 'rating' in updated and updated['rating']:
                status = 'completed'
                changes.append(Change(
                    ChangeType.PROPERTY_ADDED,
                    "Added status: completed (has rating)"
                ))
            # Default to want-to-play
            else:
                status = 'want-to-play'
                changes.append(Change(
                    ChangeType.PROPERTY_ADDED,
                    "Added status: want-to-play (default)"
                ))

            updated['status'] = status

        # Update tags in frontmatter if they changed
        if tags != original_tags:
            updated['tags'] = tags

        return updated, changes

    def format_frontmatter(self, frontmatter: Dict) -> str:
        """Format frontmatter as YAML string."""
        # Use default_flow_style=False for block style (more readable)
        yaml_str = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=float("inf")  # Prevent line wrapping
        )
        return yaml_str

    def migrate_file(self, file_path: Path) -> MigrationResult:
        """
        Migrate a single file.

        Returns:
            MigrationResult with success status and changes
        """
        self.log(f"Processing {file_path}")

        try:
            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract frontmatter
            frontmatter, body, _ = self.extract_frontmatter(content)

            if frontmatter is None:
                return MigrationResult(
                    file_path=file_path,
                    success=False,
                    changes=[],
                    error="No valid frontmatter found"
                )

            # Check for game tag
            if not self.has_game_tag(frontmatter):
                return MigrationResult(
                    file_path=file_path,
                    success=False,
                    changes=[],
                    error="Not a game note (no 'game' tag)"
                )

            # Apply migration
            updated_frontmatter, changes = self.migrate_frontmatter(frontmatter)

            # Check if anything changed
            if not changes:
                return MigrationResult(
                    file_path=file_path,
                    success=True,
                    changes=[Change(ChangeType.NO_CHANGE, "No changes needed")],
                    error=None
                )

            # Format new content
            new_yaml = self.format_frontmatter(updated_frontmatter)
            new_content = f"---\n{new_yaml}---{body}"

            return MigrationResult(
                file_path=file_path,
                success=True,
                changes=changes,
                error=None
            )

        except Exception as e:
            return MigrationResult(
                file_path=file_path,
                success=False,
                changes=[],
                error=str(e)
            )

    def apply_migration(self, file_path: Path) -> MigrationResult:
        """
        Apply migration to a file and write changes.

        Args:
            file_path: Path to file to migrate

        Returns:
            MigrationResult
        """
        result = self.migrate_file(file_path)

        if not result.success or not result.has_changes:
            return result

        try:
            # Read original content
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            # Extract and migrate
            frontmatter, body, _ = self.extract_frontmatter(original_content)
            updated_frontmatter, _ = self.migrate_frontmatter(frontmatter)

            # Format new content
            new_yaml = self.format_frontmatter(updated_frontmatter)
            new_content = f"---\n{new_yaml}---{body}"

            # Write new content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            self.log(f"Successfully migrated {file_path}")
            return result

        except Exception as e:
            return MigrationResult(
                file_path=file_path,
                success=False,
                changes=[],
                error=f"Failed to write file: {e}"
            )

    def find_game_notes(self, filter_tags: Optional[List[str]] = None) -> List[Path]:
        """
        Find all game notes in the vault.

        Args:
            filter_tags: Optional list of tags to filter by

        Returns:
            List of paths to game note files
        """
        game_notes = []

        # Walk through vault
        for root, _dirs, files in os.walk(self.vault_path):
            # Skip Templates folder
            if 'Templates' in Path(root).parts:
                continue

            for file in files:
                if not file.endswith('.md'):
                    continue

                # Skip backup files
                if '.backup.' in file:
                    continue

                file_path = Path(root) / file

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    frontmatter, _, _ = self.extract_frontmatter(content)

                    if frontmatter and self.has_game_tag(frontmatter):
                        # Apply tag filter if specified
                        if filter_tags:
                            tags = self.normalize_tags(frontmatter.get('tags', []))
                            if not any(tag in tags for tag in filter_tags):
                                continue

                        game_notes.append(file_path)

                except Exception as e:
                    self.log(f"Error reading {file_path}: {e}")

        return sorted(game_notes)


def print_result(result: MigrationResult, show_details: bool = True):
    """Print migration result for a file."""
    status_icon = "✓" if result.success else "✗"

    if result.success and result.has_changes:
        print(f"\n{status_icon} {result.file_path.name}")
        if show_details:
            for change in result.changes:
                if change.change_type != ChangeType.NO_CHANGE:
                    print(f"    • {change.description}")
    elif result.success and not result.has_changes:
        if show_details:
            print(f"\n○ {result.file_path.name} (no changes needed)")
    else:
        print(f"\n{status_icon} {result.file_path.name}")
        print(f"    Error: {result.error}")


def print_summary(results: List[MigrationResult]):
    """Print summary of migration results."""
    total = len(results)
    successful = sum(1 for r in results if r.success)
    failed = total - successful
    changed = sum(1 for r in results if r.success and r.has_changes)
    no_change = sum(1 for r in results if r.success and not r.has_changes)

    print("\n" + "=" * 80)
    print("MIGRATION SUMMARY")
    print("=" * 80)
    print(f"Total files processed: {total}")
    print(f"  ✓ Successfully migrated: {changed}")
    print(f"  ○ No changes needed: {no_change}")
    print(f"  ✗ Failed: {failed}")

    if failed > 0:
        print("\nFailed files:")
        for result in results:
            if not result.success:
                print(f"  • {result.file_path.name}: {result.error}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Migrate Obsidian game notes from tag-based to property-based system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would change
  python migrate_game_notes.py ~/vault backup.zip --dry-run

  # Actually perform migration with backup
  python migrate_game_notes.py ~/vault backup.zip

  # Process only jordan-tagged games
  python migrate_game_notes.py ~/vault backup.zip --filter-tag jordan --dry-run

  # Add custom player mapping (single player)
  python migrate_game_notes.py ~/vault backup.zip --player-mapping "bob:Bob Smith" --dry-run

  # Add custom player mapping (multiple players for one tag)
  python migrate_game_notes.py ~/vault backup.zip --player-mapping "CJK:Craig Briggs,Jon O'Donnell,Billy Kenney" --dry-run

Transformation Rules:
  1. Convert player tags (e.g., 'jordan') to wikilink properties
  2. Determine status based on 'wip' tag or 'rating' property
  3. Remove converted tags from tags list
  4. Preserve all other properties and tags
        """
    )

    parser.add_argument(
        'vault_path',
        type=str,
        help='Path to Obsidian vault'
    )

    parser.add_argument(
        'backup_filename',
        type=str,
        help='Backup filename (e.g., backup.zip)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would change without modifying files'
    )

    parser.add_argument(
        '--filter-tag',
        type=str,
        action='append',
        dest='filter_tags',
        help='Only process files with this tag (can be specified multiple times)'
    )

    parser.add_argument(
        '--player-mapping',
        type=str,
        action='append',
        dest='player_mappings',
        help='Add player tag mapping in format "tag:Name(s)". Use comma for multiple: "CJK:Craig,Jon,Billy"'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--no-summary',
        action='store_true',
        help='Don\'t show detailed output for each file (only show summary)'
    )

    args = parser.parse_args()

    # Validate vault path
    vault_path = Path(args.vault_path).expanduser()
    if not vault_path.is_dir():
        print(f"❌ Error: Vault path does not exist: {vault_path}")
        sys.exit(1)

    # Setup player mappings
    player_mapping = PlayerMapping()
    if args.player_mappings:
        for mapping in args.player_mappings:
            if ':' not in mapping:
                print(f"⚠️  Warning: Invalid player mapping format '{mapping}' (expected 'tag:Name')")
                continue
            tag, name = mapping.split(':', 1)
            player_mapping.add_mapping(tag.strip(), name.strip())
            if args.verbose:
                print(f"Added player mapping: {tag.strip()} -> {name.strip()}")

    # Create migrator
    migrator = ObsidianNoteMigrator(vault_path, player_mapping, verbose=args.verbose)

    # Print header
    mode = "DRY RUN" if args.dry_run else "MIGRATION"
    print(f"{'=' * 80}")
    print(f"Obsidian Game Notes {mode}")
    print(f"{'=' * 80}")
    print(f"Vault: {vault_path}")
    print(f"Backup: {args.backup_filename}")
    if args.filter_tags:
        print(f"Filter tags: {', '.join(args.filter_tags)}")
    print(f"{'=' * 80}")

    # Find game notes
    print("\n🔍 Scanning for game notes...")
    game_notes = migrator.find_game_notes(filter_tags=args.filter_tags)

    if not game_notes:
        print("✓ No game notes found matching criteria")
        return

    print(f"✓ Found {len(game_notes)} game note(s)")

    # Confirm before proceeding (if not dry-run)
    if not args.dry_run:
        response = input(f"\n⚠️  This will modify {len(game_notes)} file(s). Continue? (y/n): ").strip().lower()
        if response != 'y':
            print("Cancelled by user")
            return

        # Create backup before processing
        print()
        create_vault_backup(vault_path, args.backup_filename)

    print(f"{'=' * 80}")
    print(f"{'Processing files...' if not args.dry_run else 'Analyzing files...'}")
    print(f"{'=' * 80}")

    # Process files
    results = []
    for file_path in game_notes:
        if args.dry_run:
            result = migrator.migrate_file(file_path)
        else:
            result = migrator.apply_migration(file_path)

        results.append(result)

        # Print result immediately if not suppressed
        if not args.no_summary:
            print_result(result, show_details=True)

    # Print summary
    print_summary(results)

    if args.dry_run:
        print("\n💡 This was a dry run. No files were modified.")
        print("   Run without --dry-run to apply changes.")
    else:
        print("\n✅ Migration complete!")
        print(f"   Backup saved to: {args.backup_filename}")


if __name__ == "__main__":
    main()
