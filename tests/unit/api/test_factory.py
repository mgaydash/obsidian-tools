"""Unit tests for lib/api/__init__.py (MediaAPIFactory)"""

import pytest
import os
import responses

from lib.api import MediaAPIFactory, TMDBClient, IGDBClient, MusicBrainzClient


# ============================================================================
# Tests for MediaAPIFactory.create_client
# ============================================================================

def test_create_client_movie(set_mock_env):
    """Test creating TMDB client for movies."""
    client = MediaAPIFactory.create_client('movie')

    assert isinstance(client, TMDBClient)
    assert client.media_type == 'movie'


def test_create_client_tv(set_mock_env):
    """Test creating TMDB client for TV shows."""
    client = MediaAPIFactory.create_client('tv')

    assert isinstance(client, TMDBClient)
    assert client.media_type == 'tv'


@responses.activate
def test_create_client_game(set_mock_env):
    """Test creating IGDB client for games."""
    # Mock OAuth token request
    responses.add(
        responses.POST,
        'https://id.twitch.tv/oauth2/token',
        json={'access_token': 'test_token'},
        status=200
    )

    client = MediaAPIFactory.create_client('game')

    assert isinstance(client, IGDBClient)


def test_create_client_album():
    """Test creating MusicBrainz client for albums (no credentials needed)."""
    client = MediaAPIFactory.create_client('album')

    assert isinstance(client, MusicBrainzClient)


# ============================================================================
# Tests for credential validation
# ============================================================================

def test_create_client_movie_missing_api_key(clear_env_vars):
    """Test creating movie client without TMDB_API_KEY raises error."""
    with pytest.raises(ValueError) as excinfo:
        MediaAPIFactory.create_client('movie')

    assert 'TMDB_API_KEY' in str(excinfo.value)


def test_create_client_tv_missing_api_key(clear_env_vars):
    """Test creating TV client without TMDB_API_KEY raises error."""
    with pytest.raises(ValueError) as excinfo:
        MediaAPIFactory.create_client('tv')

    assert 'TMDB_API_KEY' in str(excinfo.value)


def test_create_client_game_missing_client_id(clear_env_vars, monkeypatch):
    """Test creating game client without IGDB_CLIENT_ID raises error."""
    # Set only secret, not ID
    monkeypatch.setenv('IGDB_CLIENT_SECRET', 'test_secret')

    with pytest.raises(ValueError) as excinfo:
        MediaAPIFactory.create_client('game')

    assert 'IGDB_CLIENT_ID' in str(excinfo.value)
    assert 'IGDB_CLIENT_SECRET' in str(excinfo.value)


def test_create_client_game_missing_client_secret(clear_env_vars, monkeypatch):
    """Test creating game client without IGDB_CLIENT_SECRET raises error."""
    # Set only ID, not secret
    monkeypatch.setenv('IGDB_CLIENT_ID', 'test_id')

    with pytest.raises(ValueError) as excinfo:
        MediaAPIFactory.create_client('game')

    assert 'IGDB_CLIENT_ID' in str(excinfo.value)
    assert 'IGDB_CLIENT_SECRET' in str(excinfo.value)


def test_create_client_game_missing_both_credentials(clear_env_vars):
    """Test creating game client without any IGDB credentials raises error."""
    with pytest.raises(ValueError) as excinfo:
        MediaAPIFactory.create_client('game')

    assert 'IGDB_CLIENT_ID' in str(excinfo.value)
    assert 'IGDB_CLIENT_SECRET' in str(excinfo.value)


# ============================================================================
# Tests for invalid media types
# ============================================================================

@pytest.mark.parametrize("invalid_type", [
    'music',
    'book',
    'podcast',
    'series',  # Should use 'tv' not 'series'
    '',
    'MOVIE',  # Case sensitive
    'Game',   # Case sensitive
])
def test_create_client_invalid_media_type(invalid_type, set_mock_env):
    """Test creating client with invalid media type raises error."""
    with pytest.raises(ValueError) as excinfo:
        MediaAPIFactory.create_client(invalid_type)

    assert 'Invalid media type' in str(excinfo.value)
    assert invalid_type in str(excinfo.value)


# ============================================================================
# Tests for environment variable handling
# ============================================================================

def test_create_client_uses_env_vars(monkeypatch):
    """Test that factory correctly reads environment variables."""
    custom_key = 'custom_tmdb_key_xyz'
    monkeypatch.setenv('TMDB_API_KEY', custom_key)

    client = MediaAPIFactory.create_client('movie')

    assert isinstance(client, TMDBClient)
    assert client.api_key == custom_key


@responses.activate
def test_create_client_game_uses_env_vars(monkeypatch):
    """Test that game client correctly reads IGDB credentials from environment."""
    # Mock OAuth token request
    responses.add(
        responses.POST,
        'https://id.twitch.tv/oauth2/token',
        json={'access_token': 'test_token'},
        status=200
    )

    custom_id = 'custom_client_id'
    custom_secret = 'custom_client_secret'
    monkeypatch.setenv('IGDB_CLIENT_ID', custom_id)
    monkeypatch.setenv('IGDB_CLIENT_SECRET', custom_secret)

    client = MediaAPIFactory.create_client('game')

    assert isinstance(client, IGDBClient)
    assert client.client_id == custom_id
    assert client.client_secret == custom_secret


# ============================================================================
# Tests for client instance properties
# ============================================================================

def test_tmdb_client_movie_properties(set_mock_env):
    """Test TMDB movie client has correct properties."""
    client = MediaAPIFactory.create_client('movie')

    assert hasattr(client, 'api_key')
    assert hasattr(client, 'media_type')
    assert hasattr(client, 'tmdb_base_url')
    assert client.media_type == 'movie'


def test_tmdb_client_tv_properties(set_mock_env):
    """Test TMDB TV client has correct properties."""
    client = MediaAPIFactory.create_client('tv')

    assert hasattr(client, 'api_key')
    assert hasattr(client, 'media_type')
    assert hasattr(client, 'tmdb_base_url')
    assert client.media_type == 'tv'


@responses.activate
def test_igdb_client_properties(set_mock_env):
    """Test IGDB client has correct properties."""
    # Mock OAuth token request
    responses.add(
        responses.POST,
        'https://id.twitch.tv/oauth2/token',
        json={'access_token': 'test_token'},
        status=200
    )

    client = MediaAPIFactory.create_client('game')

    assert hasattr(client, 'client_id')
    assert hasattr(client, 'client_secret')
    assert hasattr(client, 'wrapper')


def test_musicbrainz_client_properties():
    """Test MusicBrainz client has correct properties."""
    client = MediaAPIFactory.create_client('album')

    # MusicBrainz client doesn't need credentials
    assert isinstance(client, MusicBrainzClient)


# ============================================================================
# Tests for multiple client creation
# ============================================================================

@responses.activate
def test_create_multiple_different_clients(set_mock_env):
    """Test creating multiple different client types."""
    # Mock OAuth token request
    responses.add(
        responses.POST,
        'https://id.twitch.tv/oauth2/token',
        json={'access_token': 'test_token'},
        status=200
    )

    movie_client = MediaAPIFactory.create_client('movie')
    tv_client = MediaAPIFactory.create_client('tv')
    game_client = MediaAPIFactory.create_client('game')
    album_client = MediaAPIFactory.create_client('album')

    # All should be different instances
    assert movie_client is not tv_client
    assert movie_client is not game_client
    assert movie_client is not album_client

    # All should be correct types
    assert isinstance(movie_client, TMDBClient)
    assert isinstance(tv_client, TMDBClient)
    assert isinstance(game_client, IGDBClient)
    assert isinstance(album_client, MusicBrainzClient)


def test_create_same_type_multiple_times(set_mock_env):
    """Test creating same client type multiple times creates new instances."""
    client1 = MediaAPIFactory.create_client('movie')
    client2 = MediaAPIFactory.create_client('movie')

    # Should be different instances
    assert client1 is not client2

    # But same type and properties
    assert type(client1) == type(client2)
    assert client1.media_type == client2.media_type
