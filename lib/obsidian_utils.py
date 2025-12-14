"""Utilities for working with Obsidian markdown files."""

import yaml
from typing import Dict, Optional, Tuple


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
