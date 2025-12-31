#!/usr/bin/env python3
"""
Obsidian Tools - Embed Poster Images in Media Notes

One-time script to add poster image embeds at the beginning of all media notes
that have a poster property but haven't embedded it yet.
"""

import argparse
import sys
import yaml
from pathlib import Path
from typing import List, Tuple, Optional

from lib.backup import create_vault_backup
from lib.poster_utils import extract_yaml_frontmatter


class PosterEmbedder:
    """Embed poster images at the beginning of media notes."""

    def __init__(self, vault_path: Path, dry_run: bool = False):
        """
        Initialize the embedder.

        Args:
            vault_path: Path to Obsidian vault
            dry_run: If True, preview changes without applying them
        """
        self.vault_path = vault_path
        self.dry_run = dry_run
        self.changes = []

    def has_media_tag(self, file_path: Path) -> bool:
        """
        Check if file has movie, series, or game tag.

        Args:
            file_path: Path to markdown file

        Returns:
            True if file has a media tag, False otherwise
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check YAML frontmatter
            frontmatter, _ = extract_yaml_frontmatter(content)
            if frontmatter and 'tags' in frontmatter:
                tags = frontmatter['tags']
                if isinstance(tags, list):
                    tags_lower = [str(t).lower() for t in tags]
                    if any(tag in tags_lower for tag in ['movie', 'series', 'game']):
                        return True

            # Check hashtag format
            content_lower = content.lower()
            return any(tag in content_lower for tag in ['#movie', '#series', '#game'])

        except Exception:
            return False

    def needs_embed(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Check if file needs poster embed added.

        Args:
            file_path: Path to markdown file

        Returns:
            Tuple of (needs_embed: bool, poster_filename: Optional[str])
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            frontmatter, remaining = extract_yaml_frontmatter(content)

            # Must have poster property
            if not frontmatter or 'poster' not in frontmatter:
                return False, None

            poster_value = frontmatter['poster']
            if not poster_value or not str(poster_value).strip():
                return False, None

            # Extract filename from [[filename]] format
            poster_filename = str(poster_value).strip('[]')

            # Check if already embedded
            # User format: ---\n{yaml}---\n\n![[poster.jpg]]\n\n{content}
            # So remaining starts with \n and we check if it starts with ![[
            if remaining.lstrip('\n').startswith('![['):
                return False, None

            return True, poster_filename

        except Exception:
            return False, None

    def find_media_notes(self) -> List[Path]:
        """
        Find all media notes that need poster embeds.

        Returns:
            List of Path objects to media note files needing embeds
        """
        media_notes = []

        for md_file in self.vault_path.rglob('*.md'):
            # Skip Templates folder
            if 'Templates' in md_file.parts:
                continue

            # Skip backup files
            if '.backup.' in md_file.name:
                continue

            # Check if has media tag and needs embed
            if self.has_media_tag(md_file):
                needs, _ = self.needs_embed(md_file)
                if needs:
                    media_notes.append(md_file)

        return media_notes

    def process_note(self, file_path: Path) -> bool:
        """
        Add poster embed to note.

        Args:
            file_path: Path to markdown file

        Returns:
            True if successful, False if skipped or failed
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            needs, poster_filename = self.needs_embed(file_path)
            if not needs:
                return False

            frontmatter, remaining = extract_yaml_frontmatter(content)

            # Build new content with embed
            # Format: ---\n{yaml}---\n\n![[poster.jpg]]\n\n{original content}
            yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)

            # Remove leading newlines from remaining to avoid extra spacing
            remaining_stripped = remaining.lstrip('\n')

            new_content = f"---\n{yaml_str}---\n\n![[{poster_filename}]]\n\n{remaining_stripped}"

            print(f"\n{'='*80}")
            print(f"Processing: {file_path.name}")
            print(f"  Poster: {poster_filename}")

            if self.dry_run:
                print(f"  [DRY RUN] Would add embed: ![[{poster_filename}]]")
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"  ✓ Added embed")

            self.changes.append(file_path.name)
            return True

        except Exception as e:
            print(f"❌ Error processing {file_path.name}: {e}")
            return False

    def run(self) -> None:
        """Main execution method."""
        print("🖼️  Poster Embedder")
        print("=" * 80)
        print(f"Vault: {self.vault_path}")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print("=" * 80)

        # Find media notes
        print("\n🔍 Scanning for media notes...")
        media_notes = self.find_media_notes()
        print(f"✓ Found {len(media_notes)} note(s) needing embeds")

        if not media_notes:
            print("\n✓ No notes need poster embeds")
            return

        # Process each note
        success_count = 0
        for file_path in media_notes:
            if self.process_note(file_path):
                success_count += 1

        # Summary
        print("\n" + "=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        print(f"✓ Processed: {success_count}/{len(media_notes)}")

        if self.dry_run:
            print("\n💡 This was a dry run. Use without --dry-run to apply changes.")
        else:
            print("\n✅ Done!")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Embed poster images at the beginning of media notes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Dry run to preview changes
  python embed_posters.py ~/vault --dry-run

  # Apply changes with backup
  python embed_posters.py ~/vault backup.zip
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

    # Create backup (skip in dry-run)
    if not args.dry_run:
        if not args.backup_filename:
            print("❌ Backup filename required when not in dry-run mode")
            sys.exit(1)

        print("\n📦 Creating backup...")
        create_vault_backup(vault_path, args.backup_filename)
        print(f"✓ Backup created: {args.backup_filename}")

    # Run embedder
    embedder = PosterEmbedder(vault_path, dry_run=args.dry_run)
    embedder.run()


if __name__ == "__main__":
    main()
