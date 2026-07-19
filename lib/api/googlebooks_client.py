"""Google Books API client for books."""

import re
import requests
from typing import List, Dict, Optional
from .base import MediaAPIClient
from ..obsidian_utils import sanitize_filename, format_wikilink, translate_genre_tag, get_user_input


class GoogleBooksClient(MediaAPIClient):
    """Google Books API client implementation for books."""

    BASE_URL = "https://www.googleapis.com/books/v1"
    COUNTRY = "US"
    MAX_SUBJECTS = 5
    # Image sizes returned in volumeInfo.imageLinks, largest first.
    COVER_SIZES = ('extraLarge', 'large', 'medium', 'small', 'thumbnail', 'smallThumbnail')

    def __init__(self, api_key: str):
        self.api_key = api_key
        # Maps a representative volume id -> earliest year seen across its editions
        # during search(), so get_details() can report a first-edition-ish year
        # even though the representative volume's own publishedDate may be later.
        self._earliest_years = {}

    def _params(self, **extra) -> Dict:
        """Base query params shared by every request (API key + country)."""
        params = {'key': self.api_key, 'country': self.COUNTRY}
        params.update(extra)
        return params

    def search(self, title: str) -> List[Dict]:
        """Search Google Books for a book title."""
        url = f"{self.BASE_URL}/volumes"
        params = self._params(
            q=f'intitle:{title}',
            maxResults=25,
            printType='books',
        )
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            raise Exception(f"Google Books API error: {e}")

        items = response.json().get('items', []) or []

        # Google Books returns one entry per edition, so the same work can appear
        # many times. Collapse duplicates by (title, author): keep the first (most
        # relevant) edition as the representative — its id drives get_details, so
        # the note keeps that edition's description/cover — but report the earliest
        # year across the group (the closest proxy to a first-edition year that
        # Google Books exposes).
        representatives = {}
        order = []
        for item in items:
            result = self._standardize_search_item(item)
            key = (result['title'].lower(), result['author'].lower())
            if key not in representatives:
                representatives[key] = result
                order.append(key)
            else:
                rep = representatives[key]
                year = result['first_publish_year']
                if year is not None and (
                    rep['first_publish_year'] is None or year < rep['first_publish_year']
                ):
                    rep['first_publish_year'] = year

        standardized = []
        for key in order:
            rep = representatives[key]
            self._earliest_years[rep['id']] = rep['first_publish_year']
            standardized.append(rep)

        return standardized

    def _standardize_search_item(self, item: Dict) -> Dict:
        """Flatten a Google Books volume search item to our standard shape."""
        info = item.get('volumeInfo', {}) or {}

        authors = info.get('authors', []) or []
        author = ' & '.join(authors) if authors else 'Unknown'

        return {
            'id': item.get('id', ''),
            'title': info.get('title', 'Unknown'),
            'author': author,
            'first_publish_year': self._extract_year(info.get('publishedDate', '')),
            'subjects': (info.get('categories', []) or [])[:self.MAX_SUBJECTS],
            'cover_url': self._best_cover_url(info.get('imageLinks')),
        }

    def get_details(self, media_id: str) -> Dict:
        """Get detailed book information from Google Books."""
        url = f"{self.BASE_URL}/volumes/{media_id}"
        try:
            response = requests.get(url, params=self._params(), timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            raise Exception(f"Google Books API error: {e}")

        info = response.json().get('volumeInfo', {}) or {}

        authors = info.get('authors', []) or []
        author = ' & '.join(authors) if authors else 'Unknown'

        # Descriptions can contain simple HTML markup; the note is plain markdown.
        description = self._strip_html(info.get('description', '') or '').strip()

        # Prefer the earliest edition year recorded during search(); fall back to
        # this volume's own published date when called outside a search flow.
        year = self._earliest_years.get(media_id)
        if year is None:
            year = self._extract_year(info.get('publishedDate', ''))

        return {
            'id': media_id,
            'title': info.get('title', 'Unknown'),
            'author': author,
            'description': description,
            'subjects': (info.get('categories', []) or [])[:self.MAX_SUBJECTS],
            'first_publish_year': year,
            'cover_url': self._best_cover_url(info.get('imageLinks')),
            'info_link': info.get('infoLink', ''),
        }

    @staticmethod
    def _extract_year(text: str) -> Optional[int]:
        """Return the first 4-digit year found in text, or None."""
        if not text:
            return None
        match = re.search(r'\b(\d{4})\b', str(text))
        return int(match.group(1)) if match else None

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove basic HTML tags Google sometimes embeds in descriptions."""
        return re.sub(r'<[^>]+>', '', text)

    def _best_cover_url(self, image_links: Optional[Dict]) -> Optional[str]:
        """Pick the largest available cover, force HTTPS, drop the page-curl overlay."""
        if not image_links:
            return None
        for size in self.COVER_SIZES:
            url = image_links.get(size)
            if url:
                return url.replace('http://', 'https://').replace('&edge=curl', '')
        return None

    def prompt_disambiguation(self, title: str, results: List[Dict]) -> Optional[Dict]:
        """Show results and prompt user to select the correct one."""
        print(f"\n📚 Multiple results found for '{title}':")
        print("-" * 80)

        for idx, result in enumerate(results, 1):
            book_title = result.get('title', 'Unknown')
            author = result.get('author', 'Unknown')
            year = str(result.get('first_publish_year') or 'TBD')
            print(f"{idx}. {book_title} - {author} ({year})")
            print()

        print("0. Skip this file")
        print("-" * 80)

        while True:
            try:
                choice = get_user_input("Select the correct match (0 to skip): ").strip()
                choice_num = int(choice)

                if choice_num == 0:
                    return None
                if 1 <= choice_num <= len(results):
                    return results[choice_num - 1]
                print(f"Please enter a number between 0 and {len(results)}")
            except ValueError:
                print("Please enter a valid number")

    def format_note_content(self, details: Dict) -> str:
        """Generate markdown content for the book note."""
        info_link = details.get('info_link') or "Not available"

        tags = ['book']
        for subject in details.get('subjects', []) or []:
            tag = translate_genre_tag(subject)
            if tag and tag not in tags:
                tags.append(tag)

        tags_yaml = '\n'.join([f'  - {tag}' for tag in tags])

        author = details.get('author', 'Unknown')
        description = (details.get('description') or '').strip()

        if description:
            desc_text = f"{description}\n\nBy {format_wikilink(author)}."
        else:
            desc_text = f"By {format_wikilink(author)}."

        return f"""---
tags:
{tags_yaml}
---

## Links
{info_link}

## Description
{desc_text}
"""

    def get_filename(self, details: Dict) -> str:
        """Generate filename in 'Author - Title (Year).md' format."""
        author = details.get('author', 'Unknown')
        title = details.get('title', 'Unknown')
        year = details.get('first_publish_year')
        year_str = str(year) if year else 'TBD'

        author_s = sanitize_filename(author)
        title_s = sanitize_filename(title)
        return f"{author_s} - {title_s} ({year_str}).md"

    def get_poster_url(self, details: Dict) -> Optional[str]:
        """Get the cover image URL (from Google Books imageLinks)."""
        return details.get('cover_url')
