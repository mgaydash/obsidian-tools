"""Poster downloader for Obsidian media notes."""

import requests
from pathlib import Path
from typing import List, Dict, Optional
from .obsidian_utils import extract_title_and_year, filter_results_by_year, find_exact_title_match, get_user_input
from .poster_utils import download_and_resize_poster, extract_yaml_frontmatter, update_frontmatter_with_poster


class PosterDownloader:
    """Download and manage posters for media notes."""

    def __init__(self, vault_path: Path, tmdb_api_key: str, poster_width: int = 200):
        """
        Initialize poster downloader.

        Args:
            vault_path: Path to Obsidian vault
            tmdb_api_key: TMDB API key
            poster_width: Width to resize posters to (default: 200px)
        """
        self.vault_path = vault_path
        self.tmdb_api_key = tmdb_api_key
        self.poster_width = poster_width
        self.tmdb_base_url = "https://api.themoviedb.org/3"

    def get_media_type_from_tags(self, file_path: Path) -> Optional[str]:
        """
        Get media type from file tags ('movie' or 'series').

        Args:
            file_path: Path to markdown file

        Returns:
            'movie', 'series', or None if no matching tag found
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check YAML frontmatter
            frontmatter, remaining = extract_yaml_frontmatter(content)
            if frontmatter and 'tags' in frontmatter:
                tags = frontmatter['tags']
                if isinstance(tags, list):
                    tags_lower = [str(t).lower() for t in tags]
                    if 'movie' in tags_lower:
                        return 'movie'
                    if 'series' in tags_lower:
                        return 'series'

            # Check hashtag format
            full_content = content.lower()
            if '#movie' in full_content:
                return 'movie'
            if '#series' in full_content:
                return 'series'

            return None
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return None

    def already_has_poster(self, file_path: Path) -> bool:
        """Check if the file already has a poster property in frontmatter."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            frontmatter, _ = extract_yaml_frontmatter(content)
            if frontmatter and 'poster' in frontmatter:
                poster_value = frontmatter['poster']
                if poster_value and str(poster_value).strip():
                    return True

            return False
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return False

    def find_media_files(self) -> List[Tuple[Path, str]]:
        """
        Find all markdown files with movie or series tags that need posters.

        Returns:
            List of tuples (file_path, media_type)
        """
        media_files = []

        for md_file in self.vault_path.rglob('*.md'):
            media_type = self.get_media_type_from_tags(md_file)
            if not media_type:
                continue

            if self.already_has_poster(md_file):
                print(f"⊘ Skipping (already has poster): {md_file.name}")
                continue

            media_files.append((md_file, media_type))
            print(f"✓ Found: {md_file.name} [{media_type.upper()}]")

        return media_files

    def search_tmdb(self, title: str, media_type: str) -> List[Dict]:
        """
        Search TMDB for a title.

        Args:
            title: Title to search for
            media_type: 'movie' or 'series' (will be converted to 'tv' for TMDB)

        Returns:
            List of results
        """
        # Convert 'series' to 'tv' for TMDB API
        tmdb_media_type = 'tv' if media_type == 'series' else 'movie'

        url = f"{self.tmdb_base_url}/search/{tmdb_media_type}"
        params = {
            'api_key': self.tmdb_api_key,
            'query': title,
            'language': 'en-US'
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        return data.get('results', [])

    def prompt_disambiguation(self, title: str, results: List[Dict], media_type: str) -> Optional[Dict]:
        """Show results and prompt user to select the correct one."""
        emoji = '🎬' if media_type == 'movie' else '📺'
        print(f"\n{emoji} Multiple results found for '{title}':")
        print("-" * 80)

        for idx, result in enumerate(results, 1):
            # Get title (movie uses 'title', TV uses 'name')
            name = result.get('title') or result.get('name', 'Unknown')

            # Get year
            year = ''
            if 'release_date' in result and result['release_date']:
                year = result['release_date'][:4]
            elif 'first_air_date' in result and result['first_air_date']:
                year = result['first_air_date'][:4]

            overview = result.get('overview', 'No description available')[:100]

            print(f"{idx}. {name} ({year})")
            print(f"   {overview}...")
            print()

        print("0. Skip this file")
        print("-" * 80)

        while True:
            try:
                choice = get_user_input("Select the correct match (0 to skip): ").strip()
                choice_num = int(choice)

                if choice_num == 0:
                    return None
                if 1 <= choice_num <= len(results):
                    return results[choice_num - 1]
                else:
                    print(f"Please enter a number between 0 and {len(results)}")
            except ValueError:
                print("Please enter a valid number")

    def process_file(self, file_path: Path, media_type: str) -> bool:
        """
        Process a single file: search TMDB, download poster, update frontmatter.

        Args:
            file_path: Path to markdown file
            media_type: 'movie' or 'series'

        Returns:
            True if successful, False if skipped or failed
        """
        # Extract title and year from filename (remove .md extension first)
        filename_without_ext = file_path.name.replace('.md', '')
        title, year = extract_title_and_year(filename_without_ext)

        print(f"\n{'='*80}")
        print(f"Processing: {file_path.name}")
        print(f"{'='*80}")

        if year:
            print(f"📅 Detected year: {year} - will use for auto-disambiguation")

        # Search TMDB (without year in query)
        try:
            results = self.search_tmdb(title, media_type)
        except Exception as e:
            print(f"❌ Error searching TMDB: {e}")
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
            selected = self.prompt_disambiguation(title, results, media_type)
            if selected is None:
                print("⊘ Skipped by user")
                return False
        else:
            selected = results[0]
            if year:
                print(f"✓ Auto-selected the only result matching year {year}")

        # Check if poster is available
        poster_path = selected.get('poster_path')
        if not poster_path:
            print(f"❌ No poster available for this {media_type}")
            return False

        # Generate poster filename based on markdown filename
        poster_filename = file_path.stem + '.jpg'
        poster_file_path = file_path.parent / poster_filename

        # Download and resize poster
        print(f"📥 Downloading poster...")
        if not download_and_resize_poster(poster_path, poster_file_path, self.tmdb_api_key, self.poster_width):
            return False

        print(f"✓ Poster saved: {poster_filename}")

        # Update frontmatter with wikilink
        if not update_frontmatter_with_poster(file_path, poster_filename):
            return False

        print(f"✓ Frontmatter updated with poster wikilink")
        print(f"✓ Successfully processed: {file_path.name}")
        return True
