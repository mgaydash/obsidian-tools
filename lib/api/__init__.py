"""API clients for media databases."""

import os
from .base import MediaAPIClient
from .tmdb_client import TMDBClient
from .igdb_client import IGDBClient


class MediaAPIFactory:
    """Factory for creating media API clients."""

    @staticmethod
    def create_client(media_type: str) -> MediaAPIClient:
        """
        Create an API client based on media type.

        Args:
            media_type: 'movie', 'tv', or 'game'

        Returns:
            Appropriate MediaAPIClient instance

        Raises:
            ValueError: If media type is invalid or API credentials are missing
        """
        if media_type in ['movie', 'tv']:
            api_key = os.environ.get('TMDB_API_KEY')
            if not api_key:
                raise ValueError("TMDB_API_KEY environment variable not set")
            return TMDBClient(api_key, media_type)

        elif media_type == 'game':
            client_id = os.environ.get('IGDB_CLIENT_ID')
            access_token = os.environ.get('IGDB_ACCESS_TOKEN')
            if not client_id or not access_token:
                raise ValueError("IGDB_CLIENT_ID and IGDB_ACCESS_TOKEN environment variables required")
            return IGDBClient(client_id, access_token)

        else:
            raise ValueError(f"Invalid media type: {media_type}. Must be 'movie', 'tv', or 'game'")


__all__ = ['MediaAPIClient', 'MediaAPIFactory', 'TMDBClient', 'IGDBClient']
