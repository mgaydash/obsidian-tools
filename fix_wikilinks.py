#!/usr/bin/env python3
"""
Obsidian Wikilink Fixer
Fixes broken wikilinks that point to old file names (without years) by updating them
to the new format "Title (Year)" after files have been renamed.
"""

import os
import sys
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict


class WikilinkFixer:
    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.title_to_files = defaultdict(list)  # Maps "Title" -> ["Title (Year1)", "Title (Year2)", ...]

    def create_backup(self, backup_filename: str) -> None:
        """Create a zip backup of the vault."""
        print(f"Creating backup: {backup_filename}")
        with zipfile.ZipFile(backup_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.vault_path):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(self.vault_path)
                    zipf.write(file_path, arcname)
        print(f"✓ Backup created successfully\n")

    def build_title_mapping(self) -> None:
        """Build a mapping of base titles to their year-formatted versions."""
        # Pattern to match "Title (Year).md"
        pattern = re.compile(r'^(.+?)\s+\((\d{4})\)\.md$')

        for md_file in self.vault_path.rglob('*.md'):
            match = pattern.match(md_file.name)
            if match:
                base_title = match.group(1)
                year = match.group(2)
                # Store the stem without .md extension
                file_stem = md_file.stem  # e.g., "Title (Year)"
                self.title_to_files[base_title].append(file_stem)

        # Sort by year (most recent first) for each title
        for title in self.title_to_files:
            self.title_to_files[title].sort(reverse=True)

    def find_wikilinks(self, content: str) -> List[Tuple[str, str, str]]:
        """
        Find all wikilinks in content.
        Returns list of tuples: (full_match, link_target, alias_or_empty)

        Examples:
        - [[Title]] -> ("[[Title]]", "Title", "")
        - [[Title|My Alias]] -> ("[[Title|My Alias]]", "Title", "My Alias")
        """
        # Pattern to match [[target]] or [[target|alias]]
        pattern = re.compile(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]')
        matches = []

        for match in pattern.finditer(content):
            full_match = match.group(0)
            target = match.group(1)
            alias = match.group(2) if match.group(2) else ""
            matches.append((full_match, target, alias))

        return matches

    def get_replacement(self, link_target: str, alias: str) -> Tuple[str, str]:
        """
        Get the replacement for a wikilink target.
        Returns (new_full_link, matched_file) or (original, None) if no replacement needed.
        """
        # Check if this target matches a base title we have a year-version for
        if link_target in self.title_to_files:
            candidates = self.title_to_files[link_target]

            if len(candidates) == 1:
                # Only one match, use it
                matched_file = candidates[0]
                if alias:
                    return f"[[{matched_file}|{alias}]]", matched_file
                else:
                    return f"[[{matched_file}]]", matched_file
            else:
                # Multiple matches - we'll need to prompt the user
                return None, None

        # No replacement needed
        return None, None

    def prompt_disambiguation(self, link_target: str, candidates: List[str]) -> str:
        """Prompt user to select which file a link should point to."""
        print(f"\n🔗 Multiple files match the link target '{link_target}':")
        print("-" * 80)

        for idx, candidate in enumerate(candidates, 1):
            print(f"{idx}. {candidate}")

        print(f"{len(candidates) + 1}. Keep original (don't update this link)")
        print("-" * 80)

        while True:
            try:
                choice = input("Select the correct file (or keep original): ").strip()
                choice_num = int(choice)

                if choice_num == len(candidates) + 1:
                    return link_target  # Keep original
                if 1 <= choice_num <= len(candidates):
                    return candidates[choice_num - 1]
                else:
                    print(f"Please enter a number between 1 and {len(candidates) + 1}")
            except ValueError:
                print("Please enter a valid number")

    def fix_file_wikilinks(self, file_path: Path, interactive: bool = True) -> Tuple[int, int]:
        """
        Fix wikilinks in a single file.
        Returns (links_updated, ambiguous_links)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")
            return 0, 0

        original_content = content
        wikilinks = self.find_wikilinks(content)

        if not wikilinks:
            return 0, 0

        links_updated = 0
        ambiguous_links = 0
        user_choices = {}  # Cache user choices for repeated links in same file

        for full_match, target, alias in wikilinks:
            # Skip if already in year format
            if re.match(r'.+\s+\(\d{4}\)$', target):
                continue

            replacement, matched_file = self.get_replacement(target, alias)

            if replacement is None and matched_file is None:
                # Multiple candidates - need disambiguation
                if target in self.title_to_files and len(self.title_to_files[target]) > 1:
                    ambiguous_links += 1

                    if interactive:
                        # Check if we already made a choice for this target in this file
                        if target not in user_choices:
                            candidates = self.title_to_files[target]
                            chosen_file = self.prompt_disambiguation(target, candidates)
                            user_choices[target] = chosen_file
                        else:
                            chosen_file = user_choices[target]

                        # Build replacement with user's choice
                        if chosen_file != target:  # User didn't choose to keep original
                            if alias:
                                replacement = f"[[{chosen_file}|{alias}]]"
                            else:
                                replacement = f"[[{chosen_file}]]"
                        else:
                            continue  # Keep original
                    else:
                        # Non-interactive mode: skip ambiguous links
                        continue
                else:
                    # No match found, skip
                    continue

            elif replacement is None:
                # No replacement needed
                continue

            # Replace the link
            content = content.replace(full_match, replacement, 1)
            links_updated += 1

        # Write back if changes were made
        if content != original_content:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                print(f"❌ Error writing {file_path}: {e}")
                return 0, 0

        return links_updated, ambiguous_links

    def fix_all_wikilinks(self, interactive: bool = True) -> None:
        """Fix wikilinks in all markdown files in the vault."""
        total_files_processed = 0
        total_links_updated = 0
        total_ambiguous = 0
        files_with_updates = []

        all_md_files = list(self.vault_path.rglob('*.md'))

        print(f"\n🔍 Scanning {len(all_md_files)} markdown files...")
        print("-" * 80)

        for md_file in all_md_files:
            links_updated, ambiguous = self.fix_file_wikilinks(md_file, interactive)

            if links_updated > 0 or ambiguous > 0:
                total_files_processed += 1
                total_links_updated += links_updated
                total_ambiguous += ambiguous

                if links_updated > 0:
                    files_with_updates.append(md_file.name)
                    print(f"✓ {md_file.name}: Updated {links_updated} link(s)")

                if ambiguous > 0 and not interactive:
                    print(f"⚠️  {md_file.name}: Skipped {ambiguous} ambiguous link(s)")

        # Summary
        print("\n" + "=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        print(f"Files scanned: {len(all_md_files)}")
        print(f"Files with updates: {total_files_processed}")
        print(f"Links updated: {total_links_updated}")
        if total_ambiguous > 0 and not interactive:
            print(f"⚠️  Ambiguous links skipped: {total_ambiguous}")
        print("\n✅ Done!")


def main():
    if len(sys.argv) < 3:
        print("Usage: python fix_wikilinks.py <vault_path> <backup_filename> [--non-interactive]")
        print("\nExample: python fix_wikilinks.py /path/to/vault wikilink_backup.zip")
        print("\nOptions:")
        print("  --non-interactive    Skip ambiguous links instead of prompting")
        sys.exit(1)

    vault_path = sys.argv[1]
    backup_filename = sys.argv[2]
    interactive = '--non-interactive' not in sys.argv

    # Check if vault exists
    if not os.path.isdir(vault_path):
        print(f"❌ Vault path does not exist: {vault_path}")
        sys.exit(1)

    print("🔗 Obsidian Wikilink Fixer")
    print("=" * 80)
    print(f"Vault: {vault_path}")
    print(f"Backup: {backup_filename}")
    print(f"Mode: {'Interactive' if interactive else 'Non-interactive'}")
    print("=" * 80)

    fixer = WikilinkFixer(vault_path)

    # Create backup
    fixer.create_backup(backup_filename)

    # Build title mapping
    print("🔍 Building file mapping...")
    fixer.build_title_mapping()

    if not fixer.title_to_files:
        print("\n✓ No files found in 'Title (Year)' format")
        print("   (Nothing to fix - run obsidian_media_updater.py first)")
        return

    print(f"✓ Found {len(fixer.title_to_files)} base title(s) with year versions")

    # Fix wikilinks
    fixer.fix_all_wikilinks(interactive)


if __name__ == "__main__":
    main()
