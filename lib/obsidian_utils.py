"""Utilities for working with Obsidian markdown files."""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, Optional, Tuple, List


def extract_yaml_frontmatter(content: str) -> Tuple[Optional[Dict], str]:
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


def sanitize_filename(title: str) -> str:
    """Sanitize title for filesystem (remove problematic characters)."""
    return title.replace(':', ' -').replace('/', '-').replace('\\', '-')


def format_wikilink(text: str) -> str:
    """Format text as an Obsidian wikilink."""
    return f"[[{text}]]"


def extract_title_and_year(input_string: str) -> Tuple[str, Optional[str]]:
    """
    Extract title and year from input string in 'Title (Year)' format.

    Args:
        input_string: Input string, possibly with year in parentheses

    Returns:
        Tuple of (title, year) where year is None if not found

    Examples:
        "Inception (2010)" -> ("Inception", "2010")
        "Inception" -> ("Inception", None)
        "The Matrix (1999)" -> ("The Matrix", "1999")
    """
    # Match pattern: Title (Year) where Year is 4 digits
    match = re.match(r'^(.+?)\s*\((\d{4})\)\s*$', input_string)
    if match:
        return match.group(1).strip(), match.group(2)
    else:
        return input_string.strip(), None


def filter_results_by_year(results: List[Dict], year: str, media_type: str) -> List[Dict]:
    """
    Filter search results by year.

    Args:
        results: List of API search results
        year: Year to filter by (4 digits)
        media_type: 'movie', 'tv', 'series', or 'game'

    Returns:
        Filtered list of results matching the year
    """
    filtered = []
    for result in results:
        result_year = None

        if media_type in ['movie', 'tv', 'series']:
            # TMDB format
            if media_type == 'movie' and 'release_date' in result:
                result_year = result['release_date'][:4] if result['release_date'] else None
            elif media_type in ['tv', 'series'] and 'first_air_date' in result:
                result_year = result['first_air_date'][:4] if result['first_air_date'] else None
        elif media_type == 'game':
            # IGDB format - convert timestamp to year
            if 'first_release_date' in result:
                from datetime import datetime
                timestamp = result['first_release_date']
                result_year = str(datetime.fromtimestamp(timestamp).year)

        if result_year == year:
            filtered.append(result)

    return filtered


def find_exact_title_match(results: List[Dict], title: str, media_type: str) -> Optional[Dict]:
    """
    Find an exact title match in results.

    Args:
        results: List of API search results
        title: Title to match (case-insensitive)
        media_type: 'movie', 'tv', 'series', or 'game'

    Returns:
        The result if exactly one exact match is found, None otherwise
    """
    exact_matches = []
    title_lower = title.lower().strip()

    for result in results:
        result_title = None

        if media_type in ['movie', 'tv', 'series']:
            # TMDB format: movies use 'title', TV uses 'name'
            result_title = result.get('title') or result.get('name')
        elif media_type == 'game':
            # IGDB format: uses 'name'
            result_title = result.get('name')

        if result_title and result_title.lower().strip() == title_lower:
            exact_matches.append(result)

    # Only return if exactly one exact match found
    if len(exact_matches) == 1:
        return exact_matches[0]
    return None


# Cache for genre mappings config
_GENRE_MAPPINGS_CACHE: Optional[Dict[str, List[str]]] = None


def _load_genre_mappings() -> Dict[str, List[str]]:
    """
    Load genre mappings from YAML config file.

    Returns:
        Dictionary mapping obsidian tags to list of API genre strings
    """
    global _GENRE_MAPPINGS_CACHE

    if _GENRE_MAPPINGS_CACHE is not None:
        return _GENRE_MAPPINGS_CACHE

    # Get path to config file (in project root)
    config_path = Path(__file__).parent.parent / 'genre_mappings.yaml'

    if not config_path.exists():
        # Return empty dict if config doesn't exist
        _GENRE_MAPPINGS_CACHE = {}
        return _GENRE_MAPPINGS_CACHE

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            mappings = yaml.safe_load(f) or {}
            _GENRE_MAPPINGS_CACHE = mappings
            return mappings
    except Exception:
        # Return empty dict on error
        _GENRE_MAPPINGS_CACHE = {}
        return _GENRE_MAPPINGS_CACHE


def translate_genre_tag(genre: str) -> str:
    """
    Translate API genre string to Obsidian-friendly tag.

    Uses genre_mappings.yaml config to map API genre strings to clean tags.
    Falls back to sanitizing the genre if no mapping found.

    Args:
        genre: Genre string from API (TMDB or IGDB)

    Returns:
        Obsidian-friendly tag string (lowercase, no spaces/special chars)

    Examples:
        "Role-Playing (RPG)" -> "rpg"
        "Science Fiction" -> "sci-fi"
        "Action/Adventure" -> "action-adventure"
        "Unknown Genre" -> "unknown-genre"
    """
    mappings = _load_genre_mappings()
    genre_lower = genre.lower().strip()

    # Check if genre matches any mapping
    for tag, source_genres in mappings.items():
        if genre_lower in [g.lower() for g in source_genres]:
            return tag

    # No mapping found - sanitize the genre
    # Convert to lowercase and replace spaces/special chars with hyphens
    sanitized = re.sub(r'[^\w\s-]', '', genre_lower)  # Remove special chars except spaces and hyphens
    sanitized = re.sub(r'[\s_]+', '-', sanitized)     # Replace spaces/underscores with hyphens
    sanitized = re.sub(r'-+', '-', sanitized)         # Collapse multiple hyphens
    sanitized = sanitized.strip('-')                   # Remove leading/trailing hyphens

    return sanitized if sanitized else 'unknown'
