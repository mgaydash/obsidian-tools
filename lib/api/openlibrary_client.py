"""Open Library API client for books."""

import re
import requests
from typing import List, Dict, Optional
from .base import MediaAPIClient
from ..obsidian_utils import sanitize_filename, format_wikilink, translate_genre_tag, get_user_input


class OpenLibraryClient(MediaAPIClient):
    """Open Library API client implementation for books."""

    BASE_URL = "https://openlibrary.org"
    COVERS_URL = "https://covers.openlibrary.org"
    MAX_SUBJECTS = 5

    def search(self, title: str) -> List[Dict]:
        """Search Open Library for a book title."""
        url = f"{self.BASE_URL}/search.json"
        params = {
            'title': title,
            'limit': 25,
        }
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            raise Exception(f"Open Library API error: {e}")

        data = response.json()
        docs = data.get('docs', [])

        standardized = []
        for doc in docs:
            work_key = doc.get('key', '')
            work_id = work_key.replace('/works/', '') if work_key.startswith('/works/') else work_key

            authors = doc.get('author_name', []) or []
            author = ' & '.join(authors) if authors else 'Unknown'

            standardized.append({
                'id': work_id,
                'title': doc.get('title', 'Unknown'),
                'author': author,
                'first_publish_year': doc.get('first_publish_year'),
                'cover_id': doc.get('cover_i'),
                'subjects': (doc.get('subject', []) or [])[:self.MAX_SUBJECTS],
            })

        return standardized

    def get_details(self, media_id: str) -> Dict:
        """Get detailed book information from Open Library."""
        work_url = f"{self.BASE_URL}/works/{media_id}.json"
        try:
            response = requests.get(work_url, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            raise Exception(f"Open Library API error: {e}")

        work = response.json()

        title = work.get('title', 'Unknown')

        # Description can be a string or {'value': '...'}
        description = work.get('description', '')
        if isinstance(description, dict):
            description = description.get('value', '')
        description = (description or '').strip()

        # Resolve author names by following each author reference
        author_names = []
        for author_ref in work.get('authors', []) or []:
            author_obj = author_ref.get('author', {}) if isinstance(author_ref, dict) else {}
            author_key = author_obj.get('key', '') if isinstance(author_obj, dict) else ''
            if not author_key:
                continue
            try:
                ar = requests.get(f"{self.BASE_URL}{author_key}.json", timeout=15)
                ar.raise_for_status()
                name = ar.json().get('name', 'Unknown')
                if name:
                    author_names.append(name)
            except requests.RequestException:
                continue

        author = ' & '.join(author_names) if author_names else 'Unknown'

        # First cover ID, if any
        covers = work.get('covers', []) or []
        cover_id = covers[0] if covers else None

        # Subjects from the work
        subjects = (work.get('subjects', []) or [])[:self.MAX_SUBJECTS]

        # Year — try work first, then fall back to the earliest edition
        year = self._extract_year(work.get('first_publish_date', ''))
        if year is None:
            year = self._earliest_edition_year(media_id)

        return {
            'id': media_id,
            'title': title,
            'author': author,
            'description': description,
            'cover_id': cover_id,
            'subjects': subjects,
            'first_publish_year': year,
        }

    @staticmethod
    def _extract_year(text: str) -> Optional[int]:
        """Return the first 4-digit year found in text, or None."""
        if not text:
            return None
        match = re.search(r'\b(\d{4})\b', str(text))
        return int(match.group(1)) if match else None

    def _earliest_edition_year(self, work_id: str) -> Optional[int]:
        """Look up the earliest publish year across a work's editions."""
        url = f"{self.BASE_URL}/works/{work_id}/editions.json"
        try:
            response = requests.get(url, params={'limit': 50}, timeout=15)
            response.raise_for_status()
        except requests.RequestException:
            return None

        years = []
        for entry in response.json().get('entries', []) or []:
            y = self._extract_year(entry.get('publish_date', ''))
            if y is not None:
                years.append(y)
        return min(years) if years else None

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
        work_id = details.get('id')
        ol_url = f"https://openlibrary.org/works/{work_id}" if work_id else "Not available"

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
{ol_url}

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
        """Get full cover URL from Open Library Covers API."""
        cover_id = details.get('cover_id')
        if not cover_id:
            return None
        return f"{self.COVERS_URL}/b/id/{cover_id}-L.jpg"
