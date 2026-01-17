"""Unit tests for lib/poster_utils.py"""

import pytest
import responses
from pathlib import Path
from PIL import Image
import io

from lib.poster_utils import (
    download_and_resize_poster,
    extract_yaml_frontmatter,
    update_frontmatter_with_poster
)


# ============================================================================
# Tests for extract_yaml_frontmatter
# ============================================================================

def test_extract_yaml_frontmatter_valid(sample_markdown_with_yaml):
    """Test extracting valid YAML frontmatter."""
    frontmatter, remaining = extract_yaml_frontmatter(sample_markdown_with_yaml)

    assert frontmatter is not None
    assert frontmatter['title'] == 'Test Movie'
    assert frontmatter['tags'] == ['movie', 'action']
    assert 'Test Movie' in remaining


def test_extract_yaml_frontmatter_none(sample_markdown_without_yaml):
    """Test content without frontmatter."""
    frontmatter, remaining = extract_yaml_frontmatter(sample_markdown_without_yaml)

    assert frontmatter is None
    assert remaining == sample_markdown_without_yaml


def test_extract_yaml_frontmatter_malformed(sample_markdown_malformed_yaml):
    """Test malformed YAML frontmatter."""
    frontmatter, remaining = extract_yaml_frontmatter(sample_markdown_malformed_yaml)

    assert frontmatter is None
    assert remaining == sample_markdown_malformed_yaml


# ============================================================================
# Tests for download_and_resize_poster - Success Cases
# ============================================================================

@responses.activate
def test_download_and_resize_poster_rgb(tmp_path, test_images):
    """Test downloading and resizing RGB image."""
    # Create test image bytes
    img_bytes = io.BytesIO()
    test_images['rgb'].save(img_bytes, format='PNG')
    img_bytes.seek(0)

    # Mock HTTP request
    responses.add(
        responses.GET,
        'https://example.com/poster.jpg',
        body=img_bytes.read(),
        status=200,
        content_type='image/png'
    )

    output_path = tmp_path / 'output.jpg'
    result = download_and_resize_poster(
        'https://example.com/poster.jpg',
        output_path,
        poster_width=100
    )

    assert result is True
    assert output_path.exists()

    # Verify the resized image
    resized = Image.open(output_path)
    assert resized.width == 100
    assert resized.format == 'JPEG'
    # Original was 200x300, resized to 100 width should be 100x150
    assert resized.height == 150


@responses.activate
def test_download_and_resize_poster_rgba(tmp_path, test_images):
    """Test downloading and resizing RGBA image (with transparency)."""
    # Create test image bytes
    img_bytes = io.BytesIO()
    test_images['rgba'].save(img_bytes, format='PNG')
    img_bytes.seek(0)

    # Mock HTTP request
    responses.add(
        responses.GET,
        'https://example.com/poster.png',
        body=img_bytes.read(),
        status=200,
        content_type='image/png'
    )

    output_path = tmp_path / 'output.jpg'
    result = download_and_resize_poster(
        'https://example.com/poster.png',
        output_path,
        poster_width=150
    )

    assert result is True
    assert output_path.exists()

    # Verify RGBA was converted to RGB
    resized = Image.open(output_path)
    assert resized.mode == 'RGB'
    assert resized.width == 150


@responses.activate
def test_download_and_resize_poster_grayscale(tmp_path, test_images):
    """Test downloading and resizing grayscale image."""
    # Create test image bytes
    img_bytes = io.BytesIO()
    test_images['grayscale'].save(img_bytes, format='PNG')
    img_bytes.seek(0)

    # Mock HTTP request
    responses.add(
        responses.GET,
        'https://example.com/poster.png',
        body=img_bytes.read(),
        status=200
    )

    output_path = tmp_path / 'output.jpg'
    result = download_and_resize_poster(
        'https://example.com/poster.png',
        output_path,
        poster_width=200
    )

    assert result is True
    assert output_path.exists()

    # Verify grayscale was converted to RGB
    resized = Image.open(output_path)
    assert resized.mode == 'RGB'


@responses.activate
def test_download_and_resize_poster_palette(tmp_path, test_images):
    """Test downloading and resizing palette mode image."""
    # Create test image bytes
    img_bytes = io.BytesIO()
    test_images['palette'].save(img_bytes, format='PNG')
    img_bytes.seek(0)

    # Mock HTTP request
    responses.add(
        responses.GET,
        'https://example.com/poster.png',
        body=img_bytes.read(),
        status=200
    )

    output_path = tmp_path / 'output.jpg'
    result = download_and_resize_poster(
        'https://example.com/poster.png',
        output_path,
        poster_width=100
    )

    assert result is True
    assert output_path.exists()

    # Verify palette was converted to RGB
    resized = Image.open(output_path)
    assert resized.mode == 'RGB'


@responses.activate
def test_download_and_resize_poster_aspect_ratio_wide(tmp_path, test_images):
    """Test that aspect ratio is preserved for wide images."""
    # Wide image: 400x200
    img_bytes = io.BytesIO()
    test_images['wide'].save(img_bytes, format='PNG')
    img_bytes.seek(0)

    responses.add(
        responses.GET,
        'https://example.com/wide.png',
        body=img_bytes.read(),
        status=200
    )

    output_path = tmp_path / 'wide.jpg'
    result = download_and_resize_poster(
        'https://example.com/wide.png',
        output_path,
        poster_width=200
    )

    assert result is True

    # Verify aspect ratio: 400/200 = 2, so 200 width should be 100 height
    resized = Image.open(output_path)
    assert resized.width == 200
    assert resized.height == 100


@responses.activate
def test_download_and_resize_poster_aspect_ratio_tall(tmp_path, test_images):
    """Test that aspect ratio is preserved for tall images."""
    # Tall image: 200x600
    img_bytes = io.BytesIO()
    test_images['tall'].save(img_bytes, format='PNG')
    img_bytes.seek(0)

    responses.add(
        responses.GET,
        'https://example.com/tall.png',
        body=img_bytes.read(),
        status=200
    )

    output_path = tmp_path / 'tall.jpg'
    result = download_and_resize_poster(
        'https://example.com/tall.png',
        output_path,
        poster_width=100
    )

    assert result is True

    # Verify aspect ratio: 600/200 = 3, so 100 width should be 300 height
    resized = Image.open(output_path)
    assert resized.width == 100
    assert resized.height == 300


@responses.activate
def test_download_and_resize_poster_large_to_small(tmp_path, test_images):
    """Test downsizing large image."""
    # Large image: 800x1200
    img_bytes = io.BytesIO()
    test_images['large'].save(img_bytes, format='PNG')
    img_bytes.seek(0)

    responses.add(
        responses.GET,
        'https://example.com/large.png',
        body=img_bytes.read(),
        status=200
    )

    output_path = tmp_path / 'small.jpg'
    result = download_and_resize_poster(
        'https://example.com/large.png',
        output_path,
        poster_width=200
    )

    assert result is True

    resized = Image.open(output_path)
    assert resized.width == 200
    # 800x1200 aspect = 1.5, so 200 width → 300 height
    assert resized.height == 300


@responses.activate
def test_download_and_resize_poster_small_to_large(tmp_path, test_images):
    """Test upsizing small image."""
    # Small image: 50x75
    img_bytes = io.BytesIO()
    test_images['small'].save(img_bytes, format='PNG')
    img_bytes.seek(0)

    responses.add(
        responses.GET,
        'https://example.com/small.png',
        body=img_bytes.read(),
        status=200
    )

    output_path = tmp_path / 'large.jpg'
    result = download_and_resize_poster(
        'https://example.com/small.png',
        output_path,
        poster_width=200
    )

    assert result is True

    resized = Image.open(output_path)
    assert resized.width == 200
    # 50x75 aspect = 1.5, so 200 width → 300 height
    assert resized.height == 300


@responses.activate
def test_download_and_resize_poster_custom_width(tmp_path, test_images):
    """Test custom poster width parameter."""
    img_bytes = io.BytesIO()
    test_images['rgb'].save(img_bytes, format='PNG')
    img_bytes.seek(0)

    responses.add(
        responses.GET,
        'https://example.com/poster.png',
        body=img_bytes.read(),
        status=200
    )

    output_path = tmp_path / 'custom.jpg'
    result = download_and_resize_poster(
        'https://example.com/poster.png',
        output_path,
        poster_width=300
    )

    assert result is True

    resized = Image.open(output_path)
    assert resized.width == 300


# ============================================================================
# Tests for download_and_resize_poster - Error Cases
# ============================================================================

@responses.activate
def test_download_and_resize_poster_http_error(tmp_path, capsys):
    """Test handling HTTP errors."""
    responses.add(
        responses.GET,
        'https://example.com/poster.jpg',
        status=404
    )

    output_path = tmp_path / 'output.jpg'
    result = download_and_resize_poster(
        'https://example.com/poster.jpg',
        output_path
    )

    assert result is False
    assert not output_path.exists()

    # Check error message
    captured = capsys.readouterr()
    assert 'Error downloading/processing poster' in captured.out


@responses.activate
def test_download_and_resize_poster_corrupt_image(tmp_path, corrupt_image_data, capsys):
    """Test handling corrupt image data."""
    responses.add(
        responses.GET,
        'https://example.com/corrupt.jpg',
        body=corrupt_image_data,
        status=200
    )

    output_path = tmp_path / 'output.jpg'
    result = download_and_resize_poster(
        'https://example.com/corrupt.jpg',
        output_path
    )

    assert result is False
    assert not output_path.exists()

    captured = capsys.readouterr()
    assert 'Error downloading/processing poster' in captured.out


@responses.activate
def test_download_and_resize_poster_network_error(tmp_path, capsys):
    """Test handling network errors."""
    # Don't add any mock response - will cause connection error
    output_path = tmp_path / 'output.jpg'
    result = download_and_resize_poster(
        'https://invalid-url-that-does-not-exist.example.com/poster.jpg',
        output_path
    )

    assert result is False
    assert not output_path.exists()


# ============================================================================
# Tests for update_frontmatter_with_poster
# ============================================================================

def test_update_frontmatter_with_poster_existing_yaml(tmp_path, sample_markdown_with_yaml):
    """Test updating existing YAML frontmatter with poster."""
    file_path = tmp_path / 'test.md'
    file_path.write_text(sample_markdown_with_yaml)

    result = update_frontmatter_with_poster(file_path, 'Test Movie (2020).jpg')

    assert result is True

    # Read and verify
    content = file_path.read_text()
    assert 'poster: [[Test Movie (2020).jpg]]' in content
    assert 'title: Test Movie' in content
    assert 'tags:' in content


def test_update_frontmatter_with_poster_no_yaml(tmp_path, sample_markdown_without_yaml):
    """Test adding poster to file without YAML frontmatter."""
    file_path = tmp_path / 'test.md'
    file_path.write_text(sample_markdown_without_yaml)

    result = update_frontmatter_with_poster(file_path, 'poster.jpg')

    assert result is True

    # Read and verify frontmatter was added
    content = file_path.read_text()
    assert content.startswith('---')
    assert 'poster: [[poster.jpg]]' in content


def test_update_frontmatter_with_poster_replaces_existing(tmp_path):
    """Test that updating poster replaces existing poster field."""
    content = """---
title: Test Movie
poster: [[old_poster.jpg]]
---

# Content
"""
    file_path = tmp_path / 'test.md'
    file_path.write_text(content)

    result = update_frontmatter_with_poster(file_path, 'new_poster.jpg')

    assert result is True

    # Verify poster was replaced
    new_content = file_path.read_text()
    assert 'poster: [[new_poster.jpg]]' in new_content
    assert '[[old_poster.jpg]]' not in new_content


def test_update_frontmatter_with_poster_preserves_content(tmp_path, sample_markdown_with_yaml):
    """Test that content after frontmatter is preserved."""
    file_path = tmp_path / 'test.md'
    file_path.write_text(sample_markdown_with_yaml)

    original_content = sample_markdown_with_yaml.split('---', 2)[2]

    result = update_frontmatter_with_poster(file_path, 'poster.jpg')

    assert result is True

    # Verify content is preserved
    new_full_content = file_path.read_text()
    # Content after second --- should be same
    assert new_full_content.split('---', 2)[2] == original_content


def test_update_frontmatter_with_poster_file_not_found(tmp_path, capsys):
    """Test handling file not found error."""
    file_path = tmp_path / 'nonexistent.md'

    result = update_frontmatter_with_poster(file_path, 'poster.jpg')

    assert result is False

    captured = capsys.readouterr()
    assert 'Error updating frontmatter' in captured.out


def test_update_frontmatter_with_poster_malformed_yaml(tmp_path, sample_markdown_malformed_yaml):
    """Test updating file with malformed YAML creates new frontmatter."""
    file_path = tmp_path / 'test.md'
    file_path.write_text(sample_markdown_malformed_yaml)

    result = update_frontmatter_with_poster(file_path, 'poster.jpg')

    assert result is True

    # Should have created valid YAML
    content = file_path.read_text()
    assert 'poster: [[poster.jpg]]' in content
