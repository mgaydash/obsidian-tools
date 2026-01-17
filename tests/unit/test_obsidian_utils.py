"""Unit tests for lib/obsidian_utils.py"""

import pytest
import yaml
from datetime import datetime, timezone
from pathlib import Path
from freezegun import freeze_time

from lib.obsidian_utils import (
    extract_yaml_frontmatter,
    sanitize_filename,
    format_wikilink,
    extract_title_and_year,
    filter_results_by_year,
    find_exact_title_match,
    is_game_unreleased,
    translate_genre_tag,
    _load_genre_mappings
)


# ============================================================================
# Tests for extract_yaml_frontmatter
# ============================================================================

def test_extract_yaml_frontmatter_valid():
    """Test extracting valid YAML frontmatter."""
    content = """---
title: Test Movie
tags: [movie, action]
year: 2020
---

# Content here
"""
    frontmatter, remaining = extract_yaml_frontmatter(content)

    assert frontmatter is not None
    assert frontmatter['title'] == 'Test Movie'
    assert frontmatter['tags'] == ['movie', 'action']
    assert frontmatter['year'] == 2020
    assert remaining.strip() == '# Content here'


def test_extract_yaml_frontmatter_no_frontmatter():
    """Test content without frontmatter."""
    content = "# Just a heading\n\nSome content"
    frontmatter, remaining = extract_yaml_frontmatter(content)

    assert frontmatter is None
    assert remaining == content


def test_extract_yaml_frontmatter_malformed():
    """Test malformed YAML frontmatter."""
    content = """---
title: Test Movie
tags: [movie, action
year: 2020
---

# Content
"""
    frontmatter, remaining = extract_yaml_frontmatter(content)

    assert frontmatter is None
    assert remaining == content


def test_extract_yaml_frontmatter_incomplete():
    """Test incomplete frontmatter (missing closing ---)."""
    content = """---
title: Test Movie
tags: [movie]
# Content without closing ---
"""
    frontmatter, remaining = extract_yaml_frontmatter(content)

    assert frontmatter is None
    assert remaining == content


def test_extract_yaml_frontmatter_empty():
    """Test empty frontmatter."""
    content = """---
---

# Content
"""
    frontmatter, remaining = extract_yaml_frontmatter(content)

    # Empty YAML loads as None
    assert frontmatter is None
    assert '# Content' in remaining


# ============================================================================
# Tests for sanitize_filename
# ============================================================================

@pytest.mark.parametrize("input_title,expected", [
    ("Normal Title", "Normal Title"),
    ("Title: Subtitle", "Title - Subtitle"),
    ("Multiple: Colons: Here", "Multiple - Colons - Here"),
    ("Path/To/File", "Path-To-File"),
    ("Windows\\Path\\File", "Windows-Path-File"),
    ("What? Question", "What Question"),
    ("Multiple??? Questions", "Multiple Questions"),
    ("Mix: Of/Different\\Chars?", "Mix - Of-Different-Chars"),
    ("Title (2020)", "Title (2020)"),  # Parentheses are OK
    ("", ""),  # Empty string
])
def test_sanitize_filename(input_title, expected):
    """Test filename sanitization for various problematic characters."""
    assert sanitize_filename(input_title) == expected


# ============================================================================
# Tests for format_wikilink
# ============================================================================

@pytest.mark.parametrize("text,expected", [
    ("Actor Name", "[[Actor Name]]"),
    ("Movie Title", "[[Movie Title]]"),
    ("", "[[]]"),
    ("Text with spaces", "[[Text with spaces]]"),
])
def test_format_wikilink(text, expected):
    """Test wikilink formatting."""
    assert format_wikilink(text) == expected


# ============================================================================
# Tests for extract_title_and_year
# ============================================================================

@pytest.mark.parametrize("input_string,expected_title,expected_year", [
    ("Inception (2010)", "Inception", "2010"),
    ("The Matrix (1999)", "The Matrix", "1999"),
    ("Inception", "Inception", None),
    ("Movie Without Year", "Movie Without Year", None),
    ("Title (20XX)", "Title (20XX)", None),  # Invalid year format
    ("Title (999)", "Title (999)", None),  # Only 3 digits
    ("Title (10000)", "Title (10000)", None),  # 5 digits
    ("Loot (2022)", "Loot", "2022"),
    ("  Spaced Title (2020)  ", "Spaced Title", "2020"),  # Whitespace handling
    ("Multiple (Words) (2020)", "Multiple (Words)", "2020"),
    ("", "", None),  # Empty string
])
def test_extract_title_and_year(input_string, expected_title, expected_year):
    """Test title and year extraction."""
    title, year = extract_title_and_year(input_string)
    assert title == expected_title
    assert year == expected_year


# ============================================================================
# Tests for filter_results_by_year - TMDB (movies)
# ============================================================================

def test_filter_results_by_year_movie_match():
    """Test filtering movie results by year with match."""
    results = [
        {'title': 'Inception', 'release_date': '2010-07-16'},
        {'title': 'Inception', 'release_date': '2014-01-01'},
    ]
    filtered = filter_results_by_year(results, '2010', 'movie')

    assert len(filtered) == 1
    assert filtered[0]['release_date'].startswith('2010')


def test_filter_results_by_year_movie_no_match():
    """Test filtering movie results by year with no match."""
    results = [
        {'title': 'Inception', 'release_date': '2014-07-16'},
    ]
    filtered = filter_results_by_year(results, '2010', 'movie')

    assert len(filtered) == 0


def test_filter_results_by_year_movie_missing_date():
    """Test filtering movies with missing release_date."""
    results = [
        {'title': 'Movie 1', 'release_date': '2010-01-01'},
        {'title': 'Movie 2', 'release_date': None},
        {'title': 'Movie 3'},  # No release_date key
    ]
    filtered = filter_results_by_year(results, '2010', 'movie')

    assert len(filtered) == 1


# ============================================================================
# Tests for filter_results_by_year - TMDB (TV)
# ============================================================================

def test_filter_results_by_year_tv_match():
    """Test filtering TV results by year with match."""
    results = [
        {'name': 'Loot', 'first_air_date': '2022-06-24'},
        {'name': 'Other Show', 'first_air_date': '2020-01-01'},
    ]
    filtered = filter_results_by_year(results, '2022', 'tv')

    assert len(filtered) == 1
    assert filtered[0]['name'] == 'Loot'


def test_filter_results_by_year_series_alias():
    """Test that 'series' works as alias for 'tv'."""
    results = [
        {'name': 'Show', 'first_air_date': '2022-06-24'},
    ]
    filtered = filter_results_by_year(results, '2022', 'series')

    assert len(filtered) == 1


# ============================================================================
# Tests for filter_results_by_year - IGDB (games) - CRITICAL UTC TESTS
# ============================================================================

@freeze_time("2024-01-15 12:00:00", tz_offset=0)
def test_filter_results_by_year_game_utc():
    """Test filtering game results by year with UTC timezone handling."""
    # Timestamp for 2021-01-01 00:00:00 UTC
    timestamp_2021 = int(datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())
    # Timestamp for 2020-12-31 23:59:59 UTC
    timestamp_2020 = int(datetime(2020, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp())

    results = [
        {'name': 'Game 2021', 'first_release_date': timestamp_2021},
        {'name': 'Game 2020', 'first_release_date': timestamp_2020},
    ]
    filtered = filter_results_by_year(results, '2021', 'game')

    assert len(filtered) == 1
    assert filtered[0]['name'] == 'Game 2021'


@freeze_time("2024-01-15 12:00:00", tz_offset=0)
def test_filter_results_by_year_game_multiple_years():
    """Test filtering games across multiple years."""
    results = [
        {'name': 'Game 2020', 'first_release_date': 1577836800},  # 2020-01-01 UTC
        {'name': 'Game 2021', 'first_release_date': 1609459200},  # 2021-01-01 UTC
        {'name': 'Game 2022', 'first_release_date': 1640995200},  # 2022-01-01 UTC
    ]
    filtered = filter_results_by_year(results, '2021', 'game')

    assert len(filtered) == 1
    assert filtered[0]['name'] == 'Game 2021'


def test_filter_results_by_year_game_missing_date():
    """Test filtering games with missing first_release_date (unreleased)."""
    results = [
        {'name': 'Released Game', 'first_release_date': 1609459200},
        {'name': 'Unreleased Game'},  # No date
    ]
    filtered = filter_results_by_year(results, '2021', 'game')

    # Unreleased game should not match any year
    assert len(filtered) == 1
    assert filtered[0]['name'] == 'Released Game'


# ============================================================================
# Tests for filter_results_by_year - MusicBrainz (albums)
# ============================================================================

@pytest.mark.parametrize("date_string,year,should_match", [
    ("2020-06-15", "2020", True),
    ("2020-06", "2020", True),
    ("2020", "2020", True),
    ("2019-12-31", "2020", False),
    ("2021", "2020", False),
    (None, "2020", False),
    ("", "2020", False),
])
def test_filter_results_by_year_album_date_formats(date_string, year, should_match):
    """Test filtering albums with various date formats."""
    results = [{'title': 'Test Album', 'date': date_string}]
    filtered = filter_results_by_year(results, year, 'album')

    if should_match:
        assert len(filtered) == 1
    else:
        assert len(filtered) == 0


# ============================================================================
# Tests for find_exact_title_match
# ============================================================================

def test_find_exact_title_match_movie_single():
    """Test exact title match for movies with single match."""
    results = [
        {'title': 'Loot', 'release_date': '2022-01-01'},
        {'title': 'Loot - Blood Treasure', 'release_date': '2022-01-01'},
    ]
    match = find_exact_title_match(results, 'Loot', 'movie')

    assert match is not None
    assert match['title'] == 'Loot'


def test_find_exact_title_match_case_insensitive():
    """Test exact title match is case-insensitive."""
    results = [
        {'title': 'INCEPTION', 'release_date': '2010-01-01'},
    ]
    match = find_exact_title_match(results, 'inception', 'movie')

    assert match is not None
    assert match['title'] == 'INCEPTION'


def test_find_exact_title_match_whitespace():
    """Test exact title match handles whitespace."""
    results = [
        {'title': 'The Matrix', 'release_date': '1999-01-01'},
    ]
    match = find_exact_title_match(results, '  The Matrix  ', 'movie')

    assert match is not None


def test_find_exact_title_match_no_match():
    """Test exact title match with no matches."""
    results = [
        {'title': 'Similar Title', 'release_date': '2020-01-01'},
    ]
    match = find_exact_title_match(results, 'Exact Title', 'movie')

    assert match is None


def test_find_exact_title_match_multiple_exact():
    """Test exact title match with multiple exact matches returns None."""
    results = [
        {'title': 'Duplicate', 'release_date': '2020-01-01'},
        {'title': 'Duplicate', 'release_date': '2021-01-01'},
    ]
    match = find_exact_title_match(results, 'Duplicate', 'movie')

    # Should return None when multiple exact matches
    assert match is None


def test_find_exact_title_match_tv():
    """Test exact title match for TV shows using 'name'."""
    results = [
        {'name': 'Breaking Bad', 'first_air_date': '2008-01-01'},
        {'name': 'Breaking Bad: The Movie', 'first_air_date': '2020-01-01'},
    ]
    match = find_exact_title_match(results, 'Breaking Bad', 'tv')

    assert match is not None
    assert match['name'] == 'Breaking Bad'


def test_find_exact_title_match_game():
    """Test exact title match for games."""
    results = [
        {'name': 'Elden Ring'},
        {'name': 'Elden Ring: Shadow of the Erdtree'},
    ]
    match = find_exact_title_match(results, 'Elden Ring', 'game')

    assert match is not None
    assert match['name'] == 'Elden Ring'


def test_find_exact_title_match_album():
    """Test exact title match for albums."""
    results = [
        {'title': 'Abbey Road'},
        {'title': 'Abbey Road Sessions'},
    ]
    match = find_exact_title_match(results, 'Abbey Road', 'album')

    assert match is not None
    assert match['title'] == 'Abbey Road'


# ============================================================================
# Tests for is_game_unreleased
# ============================================================================

def test_is_game_unreleased_true():
    """Test detecting unreleased game."""
    game = {'name': 'Future Game', 'id': 12345}
    assert is_game_unreleased(game) is True


def test_is_game_unreleased_false():
    """Test detecting released game."""
    game = {'name': 'Released Game', 'first_release_date': 1609459200}
    assert is_game_unreleased(game) is False


# ============================================================================
# Tests for translate_genre_tag
# ============================================================================

def test_translate_genre_tag_with_mapping(tmp_path, monkeypatch):
    """Test genre translation with mapping file."""
    # Create a temporary genre_mappings.yaml
    mappings = {
        'sci-fi': ['Science Fiction', 'Sci-Fi'],
        'rpg': ['Role-Playing (RPG)', 'Role Playing'],
        'action-adventure': ['Action/Adventure']
    }

    config_path = tmp_path / 'genre_mappings.yaml'
    with open(config_path, 'w') as f:
        yaml.dump(mappings, f)

    # Mock the config path
    from lib import obsidian_utils
    original_load = obsidian_utils._load_genre_mappings

    def mock_load():
        return mappings

    monkeypatch.setattr(obsidian_utils, '_load_genre_mappings', mock_load)
    # Clear cache
    obsidian_utils._GENRE_MAPPINGS_CACHE = None

    assert translate_genre_tag('Science Fiction') == 'sci-fi'
    assert translate_genre_tag('Role-Playing (RPG)') == 'rpg'
    assert translate_genre_tag('Action/Adventure') == 'action-adventure'


def test_translate_genre_tag_without_mapping(tmp_path, monkeypatch, capsys):
    """Test genre translation falls back to sanitization."""
    from lib import obsidian_utils

    # Mock empty mappings
    monkeypatch.setattr(obsidian_utils, '_load_genre_mappings', lambda: {})
    obsidian_utils._GENRE_MAPPINGS_CACHE = None

    result = translate_genre_tag('Unknown Genre')

    assert result == 'unknown-genre'
    # Check warning was printed
    captured = capsys.readouterr()
    assert "No genre mapping for 'Unknown Genre'" in captured.out


@pytest.mark.parametrize("genre,expected", [
    ("Action/Adventure", "action-adventure"),
    ("Sci-Fi & Fantasy", "sci-fi-fantasy"),
    ("Role Playing (RPG)", "role-playing-rpg"),
    ("First Person Shooter", "first-person-shooter"),
    ("", "unknown"),  # Empty genre
])
def test_translate_genre_tag_sanitization(genre, expected, monkeypatch, capsys):
    """Test genre sanitization for various formats."""
    from lib import obsidian_utils

    # Mock empty mappings
    monkeypatch.setattr(obsidian_utils, '_load_genre_mappings', lambda: {})
    obsidian_utils._GENRE_MAPPINGS_CACHE = None

    result = translate_genre_tag(genre)
    assert result == expected


def test_load_genre_mappings_missing_file(tmp_path, monkeypatch):
    """Test loading genre mappings when config file doesn't exist."""
    from lib import obsidian_utils

    # Point to non-existent path
    fake_path = tmp_path / 'nonexistent' / 'genre_mappings.yaml'

    def mock_get_path():
        return fake_path

    # Clear cache
    obsidian_utils._GENRE_MAPPINGS_CACHE = None

    # Mock Path to point to fake location
    original_file = obsidian_utils.__file__
    monkeypatch.setattr(obsidian_utils, '__file__', str(tmp_path / 'obsidian_utils.py'))

    mappings = obsidian_utils._load_genre_mappings()

    assert mappings == {}


def test_load_genre_mappings_caches_result(tmp_path, monkeypatch):
    """Test that genre mappings are cached after first load."""
    from lib import obsidian_utils

    mappings = {'test': ['Test Genre']}

    def mock_load():
        return mappings

    monkeypatch.setattr(obsidian_utils, '_load_genre_mappings', mock_load)
    obsidian_utils._GENRE_MAPPINGS_CACHE = mappings

    # Second call should return cached result
    result = obsidian_utils._load_genre_mappings()
    assert result == mappings
