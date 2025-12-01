#!/usr/bin/env python3
"""
Obsidian Movie Poster Downloader
Finds movie notes, downloads posters from TMDB, resizes them, and updates frontmatter.
"""

import os
import sys
import re
import yaml
import zipfile
import requests
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PIL import Image
from io import BytesIO


class MoviePosterDownloader:
    def __init__(self, vault_path: str, tmdb_api_key: str, poster_width: int = 200):
        self.vault_path = Path(vault_path)
        self.tmdb_api_key = tmdb_api_key
        self.tmdb_base_url = "https://api.themoviedb.org/3"
        self.tmdb_image_base_url = "https://image.tmdb.org/t/p/original"
        self.poster_width = poster_width

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

    def has_movie_tag(self, file_path: Path) -> bool:
        """Check if file has movie tag in YAML or hashtag format."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check YAML frontmatter
            frontmatter, remaining = self.extract_yaml_frontmatter(content)
            if frontmatter and 'tags' in frontmatter:
                tags = frontmatter['tags']
                if isinstance(tags, list):
                    tags_lower = [str(t).lower() for t in tags]
                    if 'movie' in tags_lower:
                        return True

            # Check hashtag format
            full_content = content.lower()
            if '#movie' in full_content:
                return True

            return False
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return False

    def already_has_poster(self, file_path: Path) -> bool:
        """Check if the file already has a poster property in frontmatter."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            frontmatter, _ = self.extract_yaml_frontmatter(content)
            if frontmatter and 'poster' in frontmatter:
                poster_value = frontmatter['poster']
                # Check if it's not empty
                if poster_value and str(poster_value).strip():
                    return True

            return False
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return False

    def find_movie_files(self) -> List[Path]:
        """Find all markdown files with movie tag that need poster processing."""
        movie_files = []

        for md_file in self.vault_path.rglob('*.md'):
            if not self.has_movie_tag(md_file):
                continue

            if self.already_has_poster(md_file):
                print(f"⊘ Skipping (already has poster): {md_file.name}")
                continue

            movie_files.append(md_file)
            print(f"✓ Found: {md_file.name}")

        return movie_files

    def search_tmdb_movie(self, title: str) -> List[Dict]:
        """Search TMDB for a movie title. Returns list of results."""
        url = f"{self.tmdb_base_url}/search/movie"
        params = {
            'api_key': self.tmdb_api_key,
            'query': title,
            'language': 'en-US'
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        return data.get('results', [])

    def extract_title_and_year(self, filename: str) -> Tuple[str, Optional[str]]:
        """Extract title and year from filename in 'Title (Year)' format."""
        # Match pattern: Title (Year).md
        match = re.match(r'(.+?)\s*\((\d{4})\)\.md$', filename)
        if match:
            return match.group(1).strip(), match.group(2)
        else:
            # No year in filename
            return filename.replace('.md', '').strip(), None

    def prompt_disambiguation(self, title: str, results: List[Dict]) -> Optional[Dict]:
        """Show results and prompt user to select the correct one."""
        print(f"\n🎬 Multiple results found for '{title}':")
        print("-" * 80)

        for idx, result in enumerate(results, 1):
            name = result.get('title', 'Unknown')
            year = result.get('release_date', '')[:4] if result.get('release_date') else 'Unknown'
            overview = result.get('overview', 'No description available')[:100]

            print(f"{idx}. {name} ({year})")
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

    def download_and_resize_poster(self, poster_path: str, output_path: Path) -> bool:
        """Download poster from TMDB, resize it, convert to JPEG if needed."""
        try:
            # Download the image
            image_url = f"{self.tmdb_image_base_url}{poster_path}"
            response = requests.get(image_url)
            response.raise_for_status()

            # Open image with PIL
            img = Image.open(BytesIO(response.content))

            # Calculate new height maintaining aspect ratio
            aspect_ratio = img.height / img.width
            new_height = int(self.poster_width * aspect_ratio)

            # Resize image
            img_resized = img.resize((self.poster_width, new_height), Image.Resampling.LANCZOS)

            # Convert to RGB if needed (for JPEG)
            if img_resized.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img_resized.size, (255, 255, 255))
                if img_resized.mode == 'P':
                    img_resized = img_resized.convert('RGBA')
                if img_resized.mode in ('RGBA', 'LA'):
                    background.paste(img_resized, mask=img_resized.split()[-1])
                    img_resized = background
                else:
                    img_resized = img_resized.convert('RGB')
            elif img_resized.mode != 'RGB':
                img_resized = img_resized.convert('RGB')

            # Save as JPEG
            img_resized.save(output_path, 'JPEG', quality=85, optimize=True)

            return True

        except Exception as e:
            print(f"❌ Error downloading/processing poster: {e}")
            return False

    def update_frontmatter_with_poster(self, file_path: Path, poster_wikilink: str) -> bool:
        """Update the file's YAML frontmatter to include the poster wikilink."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            frontmatter, remaining_content = self.extract_yaml_frontmatter(content)

            if frontmatter is None:
                # No frontmatter exists, create it
                frontmatter = {}

            # Add poster property
            frontmatter['poster'] = poster_wikilink

            # Reconstruct the file with updated frontmatter
            yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
            new_content = f"---\n{yaml_str}---{remaining_content}"

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return True

        except Exception as e:
            print(f"❌ Error updating frontmatter: {e}")
            return False

    def process_file(self, file_path: Path) -> bool:
        """Process a single file: search TMDB, download poster, update frontmatter."""
        filename = file_path.name
        title, year = self.extract_title_and_year(filename)

        print(f"\n{'='*80}")
        print(f"Processing: {title}" + (f" ({year})" if year else ""))
        print(f"{'='*80}")

        # Search TMDB
        try:
            results = self.search_tmdb_movie(title)
        except Exception as e:
            print(f"❌ Error searching TMDB: {e}")
            return False

        if not results:
            print(f"❌ No results found for '{title}'")
            return False

        # Filter by year if we have it
        if year:
            year_filtered = [r for r in results if r.get('release_date', '').startswith(year)]
            if year_filtered:
                results = year_filtered

        # Handle disambiguation
        if len(results) > 1:
            selected = self.prompt_disambiguation(title, results)
            if selected is None:
                print("⊘ Skipped by user")
                return False
        else:
            selected = results[0]

        # Check if poster is available
        poster_path = selected.get('poster_path')
        if not poster_path:
            print(f"❌ No poster available for this movie")
            return False

        # Generate poster filename based on markdown filename
        poster_filename = file_path.stem + '.jpg'
        poster_file_path = file_path.parent / poster_filename

        # Download and resize poster
        print(f"📥 Downloading poster...")
        if not self.download_and_resize_poster(poster_path, poster_file_path):
            return False

        print(f"✓ Poster saved: {poster_filename}")

        # Update frontmatter with wikilink
        poster_wikilink = f"![[{poster_filename}]]"
        if not self.update_frontmatter_with_poster(file_path, poster_wikilink):
            return False

        print(f"✓ Frontmatter updated with poster wikilink")
        print(f"✓ Successfully processed: {filename}")
        return True


def main():
    parser = argparse.ArgumentParser(
        description='Download movie posters from TMDB for Obsidian notes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python download_movie_posters.py /path/to/vault backup_2024.zip
  python download_movie_posters.py /path/to/vault backup_2024.zip --width 300
        """
    )

    parser.add_argument('vault_path', help='Path to Obsidian vault')
    parser.add_argument('backup_filename', help='Backup filename (e.g., backup.zip)')
    parser.add_argument('--width', type=int, default=200,
                        help='Poster width in pixels (default: 200)')

    args = parser.parse_args()

    # Check if vault exists
    if not os.path.isdir(args.vault_path):
        print(f"❌ Vault path does not exist: {args.vault_path}")
        sys.exit(1)

    # Validate width
    if args.width < 50 or args.width > 2000:
        print(f"❌ Width must be between 50 and 2000 pixels")
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

    print("🎬 Obsidian Movie Poster Downloader")
    print("=" * 80)
    print(f"Vault: {args.vault_path}")
    print(f"Backup: {args.backup_filename}")
    print(f"Poster width: {args.width}px")
    print("=" * 80)

    downloader = MoviePosterDownloader(args.vault_path, tmdb_api_key, args.width)

    # Create backup
    downloader.create_backup(args.backup_filename)

    # Find movie files
    print("\n🔍 Scanning for movie files...")
    print("-" * 80)
    movie_files = downloader.find_movie_files()

    if not movie_files:
        print("\n✓ No files found that need poster processing")
        return

    print(f"\n📋 Found {len(movie_files)} file(s) to process")
    print("=" * 80)

    # Process each file
    processed_count = 0
    skipped_count = 0

    for file_path in movie_files:
        success = downloader.process_file(file_path)
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


if __name__ == "__main__":
    main()
