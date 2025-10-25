#!/usr/bin/env python3
"""
Obsidian Media File Updater
Finds movie/series notes, renames them with release year, and appends metadata from TMDB.
"""

import os
import sys
import re
import yaml
import zipfile
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class ObsidianMediaUpdater:
    def __init__(self, vault_path: str, tmdb_api_key: str):
        self.vault_path = Path(vault_path)
        self.tmdb_api_key = tmdb_api_key
        self.tmdb_base_url = "https://api.themoviedb.org/3"
        
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
    
    def extract_yaml_frontmatter(self, content: str) -> Tuple[Optional[Dict], str]:
        """Extract YAML frontmatter and return it with the remaining content."""
        if not content.startswith('---'):
            return None, content
        
        parts = content.split('---', 2)
        if len(parts) < 3:
            return None, content
        
        try:
            frontmatter = yaml.safe_load(parts[1])
            remaining_content = parts[2]
            return frontmatter, remaining_content
        except yaml.YAMLError:
            return None, content
    
    def has_media_tags(self, file_path: Path) -> bool:
        """Check if file has entertainment/movie/series tags in YAML or hashtag format."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check YAML frontmatter
            frontmatter, remaining = self.extract_yaml_frontmatter(content)
            if frontmatter and 'tags' in frontmatter:
                tags = frontmatter['tags']
                if isinstance(tags, list):
                    tags_lower = [str(t).lower() for t in tags]
                    if any(tag in tags_lower for tag in ['movie', 'series']):
                        return True
            
            # Check hashtag format
            full_content = content.lower()
            if any(tag in full_content for tag in ['#movie', '#series']):
                return True
            
            return False
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return False
    
    def is_already_formatted(self, filename: str) -> bool:
        """Check if filename is already in 'Title (year)' format."""
        # Match pattern: anything followed by space, parentheses with 4 digits
        pattern = r'.+\s\(\d{4}\)\.md$'
        return bool(re.match(pattern, filename))
    
    def find_media_files(self) -> List[Path]:
        """Find all markdown files with media tags that need processing."""
        media_files = []
        
        for md_file in self.vault_path.rglob('*.md'):
            if self.is_already_formatted(md_file.name):
                print(f"⊘ Skipping (already formatted): {md_file.name}")
                continue
            
            if self.has_media_tags(md_file):
                media_files.append(md_file)
                print(f"✓ Found: {md_file.name}")
        
        return media_files
    
    def search_tmdb(self, title: str, media_type: str = None) -> List[Dict]:
        """Search TMDB for a title. Returns list of results."""
        # Try multi-search first (searches both movies and TV)
        url = f"{self.tmdb_base_url}/search/multi"
        params = {
            'api_key': self.tmdb_api_key,
            'query': title,
            'language': 'en-US'
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Filter to only movies and TV shows
        results = [r for r in data.get('results', []) if r.get('media_type') in ['movie', 'tv']]
        return results
    
    def get_tmdb_details(self, tmdb_id: int, media_type: str) -> Dict:
        """Get detailed information from TMDB."""
        url = f"{self.tmdb_base_url}/{media_type}/{tmdb_id}"
        params = {
            'api_key': self.tmdb_api_key,
            'language': 'en-US',
            'append_to_response': 'credits,external_ids'
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def prompt_disambiguation(self, title: str, results: List[Dict]) -> Optional[Dict]:
        """Show results and prompt user to select the correct one."""
        print(f"\n📽️  Multiple results found for '{title}':")
        print("-" * 80)
        
        for idx, result in enumerate(results, 1):
            media_type = result.get('media_type', 'unknown')
            name = result.get('title') or result.get('name', 'Unknown')
            year = ''
            
            if 'release_date' in result and result['release_date']:
                year = result['release_date'][:4]
            elif 'first_air_date' in result and result['first_air_date']:
                year = result['first_air_date'][:4]
            
            overview = result.get('overview', 'No description available')[:100]
            
            print(f"{idx}. {name} ({year}) [{media_type.upper()}]")
            print(f"   {overview}...")
            print()
        
        print("0. Skip this file")
        print("-" * 80)
        
        while True:
            try:
                choice = input("Select the correct match (0 to skip): ").strip()
                choice_num = int(choice)
                
                if choice_num == 0:
                    return None
                if 1 <= choice_num <= len(results):
                    return results[choice_num - 1]
                else:
                    print(f"Please enter a number between 0 and {len(results)}")
            except ValueError:
                print("Please enter a valid number")
    
    def format_cast_as_wikilink(self, cast_member: Dict) -> str:
        """Format cast member as 'Character ([[Actor Name]])' """
        actor_name = cast_member.get('name', 'Unknown')
        character = cast_member.get('character', 'Unknown')
        return f"{character} ([[{actor_name}]])"
    
    def generate_content(self, details: Dict, media_type: str) -> str:
        """Generate the content to append to the file."""
        # Get IMDB ID and construct link
        imdb_id = details.get('external_ids', {}).get('imdb_id', '')
        imdb_link = f"https://www.imdb.com/title/{imdb_id}" if imdb_id else "Not available"
        
        # Get overview/synopsis
        overview = details.get('overview', 'No description available.')
        
        # Get director (for movies) or creator (for TV shows)
        crew = details.get('credits', {}).get('crew', [])
        directors = [c['name'] for c in crew if c.get('job') == 'Director']
        director_text = f"[[{directors[0]}]]" if directors else "Unknown"
        
        # Get top 3 cast members
        cast = details.get('credits', {}).get('cast', [])[:3]
        cast_text = ", ".join([self.format_cast_as_wikilink(c) for c in cast])
        
        # Build description
        if media_type == 'movie':
            description = f"{overview} Directed by {director_text}. Starring {cast_text}."
        else:
            # For TV shows, creators instead of directors
            creators = details.get('created_by', [])
            creator_text = f"[[{creators[0]['name']}]]" if creators else "Unknown"
            description = f"{overview} Created by {creator_text}. Starring {cast_text}."
        
        # Format the content
        content = f"""
## Links
{imdb_link}

## Description
{description}
"""
        return content
    
    def process_file(self, file_path: Path) -> bool:
        """Process a single file: search TMDB, rename, and append content."""
        title = file_path.stem
        print(f"\n{'='*80}")
        print(f"Processing: {title}")
        print(f"{'='*80}")
        
        # Search TMDB
        try:
            results = self.search_tmdb(title)
        except Exception as e:
            print(f"❌ Error searching TMDB: {e}")
            return False
        
        if not results:
            print(f"❌ No results found for '{title}'")
            return False
        
        # Handle disambiguation
        if len(results) > 1:
            selected = self.prompt_disambiguation(title, results)
            if selected is None:
                print("⊘ Skipped by user")
                return False
        else:
            selected = results[0]
        
        # Get detailed information
        media_type = selected['media_type']
        tmdb_id = selected['id']
        
        try:
            details = self.get_tmdb_details(tmdb_id, media_type)
        except Exception as e:
            print(f"❌ Error fetching details: {e}")
            return False
        
        # Get the year
        if media_type == 'movie':
            year = details.get('release_date', '')[:4]
            proper_title = details.get('title', title)
        else:  # tv
            year = details.get('first_air_date', '')[:4]
            proper_title = details.get('name', title)
        
        if not year:
            print(f"❌ Could not determine release year")
            return False
        
        # Sanitize title for filesystem (remove colons and other problematic characters)
        proper_title = proper_title.replace(':', ' -').replace('/', '-').replace('\\', '-')
        
        # Generate new filename
        new_filename = f"{proper_title} ({year}).md"
        new_path = file_path.parent / new_filename
        
        # Check if target already exists
        if new_path.exists() and new_path != file_path:
            print(f"⚠️  Target file already exists: {new_filename}")
            overwrite = input("Overwrite? (y/n): ").strip().lower()
            if overwrite != 'y':
                print("⊘ Skipped")
                return False
        
        # Read current content
        with open(file_path, 'r', encoding='utf-8') as f:
            current_content = f.read()
        
        # Generate content to append
        new_content = self.generate_content(details, media_type)
        
        # Write updated content to new file
        full_content = current_content + new_content
        with open(new_path, 'w', encoding='utf-8') as f:
            f.write(full_content)
        
        # Remove old file if renamed
        if new_path != file_path:
            file_path.unlink()
        
        print(f"✓ Successfully processed: {new_filename}")
        return True


def main():
    if len(sys.argv) != 3:
        print("Usage: python obsidian_media_updater.py <vault_path> <backup_filename>")
        print("\nExample: python obsidian_media_updater.py /path/to/vault backup_2024.zip")
        sys.exit(1)
    
    vault_path = sys.argv[1]
    backup_filename = sys.argv[2]
    
    # Check if vault exists
    if not os.path.isdir(vault_path):
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
    
    print("🎬 Obsidian Media File Updater")
    print("=" * 80)
    print(f"Vault: {vault_path}")
    print(f"Backup: {backup_filename}")
    print("=" * 80)
    
    updater = ObsidianMediaUpdater(vault_path, tmdb_api_key)
    
    # Create backup
    updater.create_backup(backup_filename)
    
    # Find media files
    print("\n🔍 Scanning for media files...")
    print("-" * 80)
    media_files = updater.find_media_files()
    
    if not media_files:
        print("\n✓ No files found that need processing")
        return
    
    print(f"\n📋 Found {len(media_files)} file(s) to process")
    print("=" * 80)
    
    # Process each file
    processed_count = 0
    skipped_count = 0
    
    for file_path in media_files:
        success = updater.process_file(file_path)
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
    print(f"📦 Backup: {backup_filename}")
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
