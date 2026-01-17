"""Shared pytest fixtures for Obsidian Tools tests."""

import pytest
from pathlib import Path
from PIL import Image
import io
import os


@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def api_responses_dir(fixtures_dir):
    """Return path to API response fixtures."""
    return fixtures_dir / "api_responses"


@pytest.fixture
def images_dir(fixtures_dir):
    """Return path to test image fixtures."""
    return fixtures_dir / "images"


@pytest.fixture
def markdown_dir(fixtures_dir):
    """Return path to markdown test fixtures."""
    return fixtures_dir / "markdown"


@pytest.fixture
def mock_tmdb_api():
    """Mock TMDB API credentials."""
    return {
        'api_key': 'test_tmdb_key_12345',
        'base_url': 'https://api.themoviedb.org/3',
        'image_base_url': 'https://image.tmdb.org/t/p/w500'
    }


@pytest.fixture
def mock_igdb_api():
    """Mock IGDB API credentials."""
    return {
        'client_id': 'test_igdb_client_id',
        'client_secret': 'test_igdb_client_secret',
        'access_token': 'test_igdb_access_token'
    }


@pytest.fixture
def mock_musicbrainz_api():
    """Mock MusicBrainz API configuration."""
    return {
        'app_name': 'obsidian-tools-test',
        'app_version': '0.1.0',
        'contact': 'test@example.com'
    }


@pytest.fixture
def temp_vault(tmp_path):
    """Create temporary vault directory structure."""
    vault = tmp_path / "test_vault"
    vault.mkdir()

    # Create subdirectories that might exist in a real vault
    (vault / "Movies").mkdir()
    (vault / "TV Shows").mkdir()
    (vault / "Games").mkdir()
    (vault / "Music").mkdir()

    return vault


@pytest.fixture
def test_images():
    """
    Generate test images in various formats for testing image processing.
    Returns dict of image name -> PIL Image object.
    """
    images = {}

    # RGB image (200x300)
    img_rgb = Image.new('RGB', (200, 300), color='red')
    images['rgb'] = img_rgb

    # RGBA image with transparency (200x300)
    img_rgba = Image.new('RGBA', (200, 300), color=(0, 255, 0, 128))
    images['rgba'] = img_rgba

    # Grayscale image (200x300)
    img_gray = Image.new('L', (200, 300), color=128)
    images['grayscale'] = img_gray

    # Palette mode image (200x300)
    img_palette = Image.new('P', (200, 300), color=42)
    images['palette'] = img_palette

    # Small image for testing resize (50x75)
    img_small = Image.new('RGB', (50, 75), color='blue')
    images['small'] = img_small

    # Large image for testing resize (800x1200)
    img_large = Image.new('RGB', (800, 1200), color='yellow')
    images['large'] = img_large

    # Wide aspect ratio (400x200)
    img_wide = Image.new('RGB', (400, 200), color='cyan')
    images['wide'] = img_wide

    # Tall aspect ratio (200x600)
    img_tall = Image.new('RGB', (200, 600), color='magenta')
    images['tall'] = img_tall

    return images


@pytest.fixture
def corrupt_image_data():
    """Return corrupted image data for testing error handling."""
    return b'This is not a valid image file'


@pytest.fixture
def sample_markdown_with_yaml():
    """Sample markdown content with YAML frontmatter."""
    return """---
title: Test Movie
tags: [movie, action]
year: 2020
---

# Test Movie

This is the movie content.
"""


@pytest.fixture
def sample_markdown_without_yaml():
    """Sample markdown content without YAML frontmatter."""
    return """# Test Movie

This is the movie content without frontmatter.
"""


@pytest.fixture
def sample_markdown_malformed_yaml():
    """Sample markdown with malformed YAML frontmatter."""
    return """---
title: Test Movie
tags: [movie, action
year: 2020
---

# Test Movie

This is the movie content.
"""


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for API keys."""
    return {
        'TMDB_API_KEY': 'test_tmdb_key',
        'IGDB_CLIENT_ID': 'test_igdb_client',
        'IGDB_CLIENT_SECRET': 'test_igdb_secret'
    }


@pytest.fixture
def set_mock_env(mock_env_vars, monkeypatch):
    """Set mock environment variables."""
    for key, value in mock_env_vars.items():
        monkeypatch.setenv(key, value)
    return mock_env_vars


@pytest.fixture
def clear_env_vars(monkeypatch):
    """Clear all API-related environment variables."""
    for key in ['TMDB_API_KEY', 'IGDB_CLIENT_ID', 'IGDB_CLIENT_SECRET']:
        monkeypatch.delenv(key, raising=False)
