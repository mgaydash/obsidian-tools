"""Utilities for downloading and processing media posters."""

import requests
import yaml
from pathlib import Path
from typing import Dict, Optional, Tuple
from PIL import Image
from io import BytesIO


def download_and_resize_poster(
    poster_url: str,
    output_path: Path,
    poster_width: int = 200,
    tmdb_api_key: str = None
) -> bool:
    """
    Download poster from URL, resize it, convert to JPEG.

    Args:
        poster_url: Full URL to poster image (TMDB, IGDB, or other source)
        output_path: Where to save the processed poster
        poster_width: Width to resize to in pixels (default: 200)
        tmdb_api_key: Deprecated, kept for backward compatibility

    Returns:
        True if successful, False otherwise
    """
    try:
        # Download the image from provided URL
        response = requests.get(poster_url)
        response.raise_for_status()

        # Open image with PIL
        img = Image.open(BytesIO(response.content))

        # Calculate new height maintaining aspect ratio
        aspect_ratio = img.height / img.width
        new_height = int(poster_width * aspect_ratio)

        # Resize image
        img_resized = img.resize((poster_width, new_height), Image.Resampling.LANCZOS)

        # Convert to RGB if needed (for JPEG)
        if img_resized.mode in ('RGBA', 'LA', 'P'):
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


def extract_yaml_frontmatter(content: str) -> Tuple[Optional[Dict], str]:
    """
    Extract YAML frontmatter and return it with the remaining content.

    Args:
        content: Full markdown file content

    Returns:
        Tuple of (frontmatter_dict, remaining_content)
    """
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


def update_frontmatter_with_poster(file_path: Path, poster_filename: str) -> bool:
    """
    Update the file's YAML frontmatter to include the poster wikilink.

    Args:
        file_path: Path to markdown file
        poster_filename: Name of poster file (e.g., 'Movie (2020).jpg')

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        frontmatter, remaining_content = extract_yaml_frontmatter(content)

        if frontmatter is None:
            frontmatter = {}

        # Add poster property with wikilink
        frontmatter['poster'] = f"[[{poster_filename}]]"

        # Reconstruct the file with updated frontmatter
        yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        new_content = f"---\n{yaml_str}---{remaining_content}"

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return True

    except Exception as e:
        print(f"❌ Error updating frontmatter: {e}")
        return False
