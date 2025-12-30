"""Base interface for media API clients."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class MediaAPIClient(ABC):
    """Abstract base class for media API clients."""

    @abstractmethod
    def search(self, title: str) -> List[Dict]:
        """
        Search for a title, return list of results.

        Args:
            title: The title to search for

        Returns:
            List of result dictionaries
        """
        pass

    @abstractmethod
    def get_details(self, media_id: str) -> Dict:
        """
        Get detailed information for a media item.

        Args:
            media_id: The ID of the media item

        Returns:
            Dictionary with detailed information
        """
        pass

    @abstractmethod
    def prompt_disambiguation(self, title: str, results: List[Dict]) -> Optional[Dict]:
        """
        Prompt user to select from multiple results.

        Args:
            title: The title that was searched for
            results: List of result dictionaries

        Returns:
            The selected result, or None if user skipped
        """
        pass

    @abstractmethod
    def format_note_content(self, details: Dict) -> str:
        """
        Generate markdown content for the note.

        Args:
            details: Detailed information about the media item

        Returns:
            Markdown formatted content
        """
        pass

    @abstractmethod
    def get_filename(self, details: Dict) -> str:
        """
        Generate filename in 'Title (Year).md' format.

        Args:
            details: Detailed information about the media item

        Returns:
            Sanitized filename
        """
        pass

    @abstractmethod
    def get_poster_url(self, details: Dict) -> Optional[str]:
        """
        Get full poster URL from media details.

        Args:
            details: Detailed information about the media item

        Returns:
            Full URL to poster image, or None if no poster available
        """
        pass
