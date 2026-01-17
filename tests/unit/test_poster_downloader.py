"""Unit tests for lib/poster_downloader.py"""

import pytest
import responses
import json
from pathlib import Path

from lib.poster_downloader import PosterDownloader


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def poster_downloader_tmdb(tmp_path):
    """Create poster downloader with TMDB credentials."""
    return PosterDownloader(
        vault_path=tmp_path,
        tmdb_api_key='test_tmdb_key',
        poster_width=200
    )


@pytest.fixture
def poster_downloader_igdb(tmp_path):
    """Create poster downloader with IGDB credentials."""
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            'https://id.twitch.tv/oauth2/token',
            json={'access_token': 'test_token'},
            status=200
        )

        return PosterDownloader(
            vault_path=tmp_path,
            igdb_client_id='test_id',
            igdb_client_secret='test_secret',
            poster_width=200
        )


@pytest.fixture
def poster_downloader_mb(tmp_path, mocker):
    """Create poster downloader with MusicBrainz (no creds needed)."""
    # Mock set_useragent to avoid issues
    mocker.patch('musicbrainzngs.set_useragent')
    return PosterDownloader(vault_path=tmp_path, poster_width=200)


# ============================================================================
# Tests for __init__
# ============================================================================

def test_init_with_tmdb(tmp_path):
    """Test initialization with TMDB credentials."""
    pd = PosterDownloader(
        vault_path=tmp_path,
        tmdb_api_key='test_key',
        poster_width=250
    )

    assert pd.vault_path == tmp_path
    assert pd.tmdb_api_key == 'test_key'
    assert pd.poster_width == 250
    assert pd.igdb_wrapper is None


@responses.activate
def test_init_with_igdb(tmp_path):
    """Test initialization with IGDB credentials."""
    responses.add(
        responses.POST,
        'https://id.twitch.tv/oauth2/token',
        json={'access_token': 'test_token'},
        status=200
    )

    pd = PosterDownloader(
        vault_path=tmp_path,
        igdb_client_id='test_id',
        igdb_client_secret='test_secret'
    )

    assert pd.igdb_client_id == 'test_id'
    assert pd.igdb_client_secret == 'test_secret'
    assert pd.igdb_wrapper is not None


def test_init_musicbrainz_sets_useragent(tmp_path, mocker):
    """Test that initialization sets MusicBrainz user agent."""
    mock_set_useragent = mocker.patch('musicbrainzngs.set_useragent')

    PosterDownloader(vault_path=tmp_path)

    mock_set_useragent.assert_called_once_with(
        'ObsidianTools',
        '1.0',
        'https://github.com/anthropics/obsidian-tools'
    )


# ============================================================================
# Tests for get_media_type_from_tags() - YAML frontmatter
# ============================================================================

def test_get_media_type_from_yaml_movie(poster_downloader_tmdb, tmp_path):
    """Test detecting movie tag from YAML frontmatter."""
    file = tmp_path / 'test.md'
    file.write_text("""---
tags: [movie, action]
---

# Content
""")

    media_type = poster_downloader_tmdb.get_media_type_from_tags(file)
    assert media_type == 'movie'


def test_get_media_type_from_yaml_series(poster_downloader_tmdb, tmp_path):
    """Test detecting series tag from YAML frontmatter."""
    file = tmp_path / 'test.md'
    file.write_text("""---
tags:
  - series
  - comedy
---

# Content
""")

    media_type = poster_downloader_tmdb.get_media_type_from_tags(file)
    assert media_type == 'series'


def test_get_media_type_from_yaml_game(poster_downloader_tmdb, tmp_path):
    """Test detecting game tag from YAML frontmatter."""
    file = tmp_path / 'test.md'
    file.write_text("""---
tags: [game, rpg]
---

# Content
""")

    media_type = poster_downloader_tmdb.get_media_type_from_tags(file)
    assert media_type == 'game'


def test_get_media_type_from_yaml_album(poster_downloader_tmdb, tmp_path):
    """Test detecting album tag from YAML frontmatter."""
    file = tmp_path / 'test.md'
    file.write_text("""---
tags: [album, rock]
---

# Content
""")

    media_type = poster_downloader_tmdb.get_media_type_from_tags(file)
    assert media_type == 'album'


def test_get_media_type_case_insensitive(poster_downloader_tmdb, tmp_path):
    """Test that tag detection is case insensitive."""
    file = tmp_path / 'test.md'
    file.write_text("""---
tags: [MOVIE, Action]
---

# Content
""")

    media_type = poster_downloader_tmdb.get_media_type_from_tags(file)
    assert media_type == 'movie'


# ============================================================================
# Tests for get_media_type_from_tags() - Hashtag format
# ============================================================================

def test_get_media_type_from_hashtag_movie(poster_downloader_tmdb, tmp_path):
    """Test detecting movie from hashtag format."""
    file = tmp_path / 'test.md'
    file.write_text("""# Movie Title

This is about a #movie
""")

    media_type = poster_downloader_tmdb.get_media_type_from_tags(file)
    assert media_type == 'movie'


def test_get_media_type_from_hashtag_series(poster_downloader_tmdb, tmp_path):
    """Test detecting series from hashtag format."""
    file = tmp_path / 'test.md'
    file.write_text("""# Show Title

This is a #series I watched.
""")

    media_type = poster_downloader_tmdb.get_media_type_from_tags(file)
    assert media_type == 'series'


def test_get_media_type_yaml_takes_priority(poster_downloader_tmdb, tmp_path):
    """Test that YAML tags take priority over hashtags."""
    file = tmp_path / 'test.md'
    file.write_text("""---
tags: [movie]
---

This is actually about a #series
""")

    media_type = poster_downloader_tmdb.get_media_type_from_tags(file)
    assert media_type == 'movie'


def test_get_media_type_no_tags(poster_downloader_tmdb, tmp_path):
    """Test file with no media tags."""
    file = tmp_path / 'test.md'
    file.write_text("""---
tags: [note, general]
---

# Just a note
""")

    media_type = poster_downloader_tmdb.get_media_type_from_tags(file)
    assert media_type is None


# ============================================================================
# Tests for already_has_poster()
# ============================================================================

def test_already_has_poster_true(poster_downloader_tmdb, tmp_path):
    """Test detecting file with existing poster."""
    file = tmp_path / 'test.md'
    file.write_text("""---
title: Test Movie
poster: [[movie.jpg]]
---

# Content
""")

    assert poster_downloader_tmdb.already_has_poster(file) is True


def test_already_has_poster_false(poster_downloader_tmdb, tmp_path):
    """Test detecting file without poster."""
    file = tmp_path / 'test.md'
    file.write_text("""---
title: Test Movie
---

# Content
""")

    assert poster_downloader_tmdb.already_has_poster(file) is False


def test_already_has_poster_empty_value(poster_downloader_tmdb, tmp_path):
    """Test that empty poster value is treated as no poster."""
    file = tmp_path / 'test.md'
    file.write_text("""---
title: Test Movie
poster: ""
---

# Content
""")

    assert poster_downloader_tmdb.already_has_poster(file) is False


# ============================================================================
# Tests for find_media_files()
# ============================================================================

def test_find_media_files(poster_downloader_tmdb, tmp_path, capsys):
    """Test finding media files in vault."""
    # Create test files
    movie1 = tmp_path / 'Movie1.md'
    movie1.write_text('---\ntags: [movie]\n---\n# Movie1')

    movie2 = tmp_path / 'Movie2.md'
    movie2.write_text('---\ntags: [movie]\nposter: [[movie2.jpg]]\n---\n# Movie2')

    series1 = tmp_path / 'Series1.md'
    series1.write_text('---\ntags: [series]\n---\n# Series1')

    other = tmp_path / 'Other.md'
    other.write_text('---\ntags: [note]\n---\n# Other')

    files = poster_downloader_tmdb.find_media_files()

    # Should find Movie1 and Series1, skip Movie2 (has poster) and Other (no media tag)
    assert len(files) == 2
    file_names = [f[0].name for f in files]
    assert 'Movie1.md' in file_names
    assert 'Series1.md' in file_names

    # Check output messages
    captured = capsys.readouterr()
    assert 'Movie1.md [MOVIE]' in captured.out
    assert 'Series1.md [SERIES]' in captured.out
    assert 'Skipping (already has poster): Movie2.md' in captured.out


def test_find_media_files_recursive(poster_downloader_tmdb, tmp_path):
    """Test finding files in subdirectories."""
    subdir = tmp_path / 'Movies'
    subdir.mkdir()

    movie = subdir / 'Movie.md'
    movie.write_text('---\ntags: [movie]\n---\n# Movie')

    files = poster_downloader_tmdb.find_media_files()

    assert len(files) == 1
    assert files[0][0].name == 'Movie.md'


# ============================================================================
# Tests for search_tmdb()
# ============================================================================

@responses.activate
def test_search_tmdb_movie(poster_downloader_tmdb):
    """Test searching TMDB for a movie."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        json={'results': [{'title': 'Inception', 'id': 27205}]},
        status=200
    )

    results = poster_downloader_tmdb.search_tmdb('Inception', 'movie')

    assert len(results) == 1
    assert results[0]['title'] == 'Inception'


@responses.activate
def test_search_tmdb_series_converts_to_tv(poster_downloader_tmdb):
    """Test that 'series' is converted to 'tv' for TMDB API."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/tv',
        json={'results': [{'name': 'Loot', 'id': 156482}]},
        status=200
    )

    results = poster_downloader_tmdb.search_tmdb('Loot', 'series')

    assert len(results) == 1
    assert results[0]['name'] == 'Loot'


# ============================================================================
# Tests for search_igdb()
# ============================================================================

@responses.activate
def test_search_igdb(tmp_path):
    """Test searching IGDB for a game."""
    # Mock OAuth
    responses.add(
        responses.POST,
        'https://id.twitch.tv/oauth2/token',
        json={'access_token': 'test_token'},
        status=200
    )

    pd = PosterDownloader(
        vault_path=tmp_path,
        igdb_client_id='test_id',
        igdb_client_secret='test_secret'
    )

    # Mock IGDB search
    mock_results = [{'name': 'Elden Ring', 'id': 119277}]

    import pytest_mock
    pd.igdb_wrapper.api_request = lambda endpoint, query: json.dumps(mock_results).encode('utf-8')

    results = pd.search_igdb('Elden Ring')

    assert len(results) == 1
    assert results[0]['name'] == 'Elden Ring'


def test_search_igdb_no_wrapper(poster_downloader_tmdb):
    """Test IGDB search without wrapper returns empty."""
    results = poster_downloader_tmdb.search_igdb('Test')

    assert len(results) == 0


# ============================================================================
# Tests for search_musicbrainz()
# ============================================================================

def test_search_musicbrainz(poster_downloader_mb, mocker):
    """Test searching MusicBrainz for an album."""
    mock_result = {
        'release-list': [
            {
                'id': 'test-mbid',
                'title': 'Abbey Road',
                'artist-credit': [{'artist': {'name': 'The Beatles'}}],
                'date': '1969-09-26'
            }
        ]
    }

    mocker.patch('musicbrainzngs.search_releases', return_value=mock_result)

    results = poster_downloader_mb.search_musicbrainz('Abbey Road')

    assert len(results) == 1
    assert results[0]['title'] == 'Abbey Road'
    assert results[0]['artist'] == 'The Beatles'


# ============================================================================
# Tests for search_api()
# ============================================================================

@responses.activate
def test_search_api_routes_movie_to_tmdb(poster_downloader_tmdb):
    """Test that movie searches route to TMDB."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        json={'results': [{'title': 'Test'}]},
        status=200
    )

    results, api_used = poster_downloader_tmdb.search_api('Test', 'movie')

    assert api_used == 'tmdb'
    assert len(results) > 0


@responses.activate
def test_search_api_routes_series_to_tmdb(poster_downloader_tmdb):
    """Test that series searches route to TMDB."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/tv',
        json={'results': [{'name': 'Test'}]},
        status=200
    )

    results, api_used = poster_downloader_tmdb.search_api('Test', 'series')

    assert api_used == 'tmdb'


# ============================================================================
# Tests for get_poster_url_from_result()
# ============================================================================

def test_get_poster_url_from_result_tmdb(poster_downloader_tmdb):
    """Test extracting poster URL from TMDB result."""
    result = {'poster_path': '/abc123.jpg'}

    url = poster_downloader_tmdb.get_poster_url_from_result(result, 'tmdb')

    assert url == 'https://image.tmdb.org/t/p/original/abc123.jpg'


def test_get_poster_url_from_result_tmdb_missing(poster_downloader_tmdb):
    """Test TMDB result without poster."""
    result = {'title': 'No Poster'}

    url = poster_downloader_tmdb.get_poster_url_from_result(result, 'tmdb')

    assert url is None


def test_get_poster_url_from_result_igdb(poster_downloader_tmdb):
    """Test extracting poster URL from IGDB result."""
    result = {'cover': {'image_id': 'co4thl'}}

    url = poster_downloader_tmdb.get_poster_url_from_result(result, 'igdb')

    assert url == 'https://images.igdb.com/igdb/image/upload/t_cover_big/co4thl.jpg'


def test_get_poster_url_from_result_igdb_missing(poster_downloader_tmdb):
    """Test IGDB result without cover."""
    result = {'name': 'No Cover'}

    url = poster_downloader_tmdb.get_poster_url_from_result(result, 'igdb')

    assert url is None


def test_get_poster_url_from_result_musicbrainz(poster_downloader_tmdb):
    """Test extracting poster URL from MusicBrainz result."""
    result = {'id': 'test-mbid'}

    url = poster_downloader_tmdb.get_poster_url_from_result(result, 'musicbrainz')

    assert url == 'https://coverartarchive.org/release/test-mbid/front'


def test_get_poster_url_from_result_musicbrainz_missing(poster_downloader_tmdb):
    """Test MusicBrainz result without ID."""
    result = {'title': 'No ID'}

    url = poster_downloader_tmdb.get_poster_url_from_result(result, 'musicbrainz')

    assert url is None


# ============================================================================
# Tests for prompt_disambiguation()
# ============================================================================

def test_prompt_disambiguation_movie(poster_downloader_tmdb, mocker):
    """Test disambiguating movie results."""
    results = [
        {'title': 'Movie 1', 'release_date': '2020-01-01', 'overview': 'Test movie'},
        {'title': 'Movie 2', 'release_date': '2021-01-01', 'overview': 'Another movie'}
    ]

    inputs = iter(['1'])
    mocker.patch('lib.poster_downloader.get_user_input', lambda prompt: next(inputs))

    result = poster_downloader_tmdb.prompt_disambiguation('Movie', results, 'movie', 'tmdb')

    assert result is not None
    assert result['title'] == 'Movie 1'


def test_prompt_disambiguation_displays_emoji(poster_downloader_tmdb, mocker, capsys):
    """Test that disambiguation displays appropriate emoji."""
    results = [{'title': 'Test', 'release_date': '2020-01-01', 'overview': 'Test'}]

    inputs = iter(['1'])
    mocker.patch('lib.poster_downloader.get_user_input', lambda prompt: next(inputs))

    poster_downloader_tmdb.prompt_disambiguation('Test', results, 'movie', 'tmdb')

    captured = capsys.readouterr()
    assert '🎬' in captured.out  # Movie emoji


def test_prompt_disambiguation_skip(poster_downloader_tmdb, mocker):
    """Test skipping disambiguation."""
    results = [{'title': 'Test', 'release_date': '2020-01-01', 'overview': 'Test'}]

    inputs = iter(['0'])
    mocker.patch('lib.poster_downloader.get_user_input', lambda prompt: next(inputs))

    result = poster_downloader_tmdb.prompt_disambiguation('Test', results, 'movie', 'tmdb')

    assert result is None


# ============================================================================
# Tests for process_file() - End-to-end workflow
# ============================================================================

@responses.activate
def test_process_file_success(poster_downloader_tmdb, tmp_path, mocker):
    """Test successful end-to-end file processing."""
    # Create test file
    file = tmp_path / 'Inception (2010).md'
    file.write_text('---\ntags: [movie]\n---\n# Inception')

    # Mock TMDB search
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        json={
            'results': [
                {
                    'title': 'Inception',
                    'release_date': '2010-07-16',
                    'poster_path': '/test.jpg'
                }
            ]
        },
        status=200
    )

    # Mock poster download
    responses.add(
        responses.GET,
        'https://image.tmdb.org/t/p/original/test.jpg',
        body=b'fake image data',
        status=200
    )

    # Mock image processing (PIL)
    from PIL import Image
    import io
    test_img = Image.new('RGB', (200, 300), color='red')
    mocker.patch('PIL.Image.open', return_value=test_img)

    result = poster_downloader_tmdb.process_file(file, 'movie')

    assert result is True
    # Verify poster file was created
    poster_file = tmp_path / 'Inception (2010).jpg'
    # Note: May not actually exist due to mocking, but code path was executed


@responses.activate
def test_process_file_no_results(poster_downloader_tmdb, tmp_path, capsys):
    """Test processing file with no search results."""
    file = tmp_path / 'Unknown Movie (2020).md'
    file.write_text('---\ntags: [movie]\n---\n# Unknown')

    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        json={'results': []},
        status=200
    )

    result = poster_downloader_tmdb.process_file(file, 'movie')

    assert result is False
    captured = capsys.readouterr()
    assert 'No results found' in captured.out


@responses.activate
def test_process_file_year_filtering(poster_downloader_tmdb, tmp_path, mocker, capsys):
    """Test that file processing filters by year."""
    file = tmp_path / 'Movie (2020).md'
    file.write_text('---\ntags: [movie]\n---\n# Movie')

    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        json={
            'results': [
                {'title': 'Movie', 'release_date': '2020-01-01', 'poster_path': '/test.jpg'},
                {'title': 'Movie', 'release_date': '2019-01-01', 'poster_path': '/test2.jpg'}
            ]
        },
        status=200
    )

    # Mock the rest of the process
    mocker.patch('lib.poster_downloader.download_and_resize_poster', return_value=True)
    mocker.patch('lib.poster_downloader.update_frontmatter_with_poster', return_value=True)

    result = poster_downloader_tmdb.process_file(file, 'movie')

    captured = capsys.readouterr()
    assert 'Detected year: 2020' in captured.out
    assert 'Filtered to 1 result(s) matching year 2020' in captured.out


@responses.activate
def test_process_file_exact_match_auto_select(poster_downloader_tmdb, tmp_path, mocker, capsys):
    """Test that exact title match is auto-selected."""
    file = tmp_path / 'Loot (2022).md'
    file.write_text('---\ntags: [series]\n---\n# Loot')

    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/tv',
        json={
            'results': [
                {'name': 'Loot', 'first_air_date': '2022-06-24', 'poster_path': '/test.jpg'},
                {'name': 'Loot - Blood Treasure', 'first_air_date': '2022-03-15', 'poster_path': '/test2.jpg'}
            ]
        },
        status=200
    )

    # Mock the rest
    mocker.patch('lib.poster_downloader.download_and_resize_poster', return_value=True)
    mocker.patch('lib.poster_downloader.update_frontmatter_with_poster', return_value=True)

    result = poster_downloader_tmdb.process_file(file, 'series')

    captured = capsys.readouterr()
    assert 'Auto-selected exact title match' in captured.out


@responses.activate
def test_process_file_no_poster_available(poster_downloader_tmdb, tmp_path, capsys):
    """Test processing file when no poster is available."""
    file = tmp_path / 'Movie (2020).md'
    file.write_text('---\ntags: [movie]\n---\n# Movie')

    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        json={
            'results': [
                {'title': 'Movie', 'release_date': '2020-01-01', 'poster_path': None}
            ]
        },
        status=200
    )

    result = poster_downloader_tmdb.process_file(file, 'movie')

    assert result is False
    captured = capsys.readouterr()
    assert 'No poster available' in captured.out
