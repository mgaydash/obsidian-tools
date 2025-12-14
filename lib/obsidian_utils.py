"""Utilities for working with Obsidian markdown files."""

import re
import yaml
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
