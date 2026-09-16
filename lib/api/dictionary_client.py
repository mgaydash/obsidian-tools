"""Free Dictionary API client for word lookups."""

import re
from typing import Dict, List, Optional
from urllib.parse import quote

import requests

from ..obsidian_utils import (
    build_frontmatter,
    format_wikilink,
    get_user_input,
    sanitize_filename,
)
from .base import MediaAPIClient

# Primary source: community proxy over Wiktionary, richer (IPA, audio, synonyms)
DICTIONARY_API_URL = 'https://api.dictionaryapi.dev/api/v2/entries/en'
# Fallback: Wikimedia's own endpoint over the same Wiktionary content. Thinner
# (no pronunciation or synonyms) but far more reliable than the community proxy,
# which returns 5xx often enough to matter.
WIKTIONARY_API_URL = 'https://en.wiktionary.org/api/rest_v1/page/definition'

# Both sources serve Wiktionary text, so one attribution covers either path
WIKTIONARY_LICENSE = 'CC BY-SA 3.0'
USER_AGENT = 'ObsidianTools/1.0 (https://github.com/mgaydash/obsidian-tools)'

# The primary's usual failure is a hang, not a refusal, so it gets the shorter
# budget: the time is pure dead wait before falling back
PRIMARY_TIMEOUT = 8
FALLBACK_TIMEOUT = 15


class DictionaryClient(MediaAPIClient):
    """Free Dictionary API client implementation (word lookups)."""

    def __init__(self):
        """Initialize the dictionary client."""
        # Both sources return everything in one response, so search() caches
        # entries for get_details() instead of making a second request
        self._entries: Dict[str, Dict] = {}
        # One client handles a whole batch of words. Once the primary has failed
        # it is almost certainly down for the rest of the run, so stop paying the
        # timeout for every remaining word.
        self._primary_failed = False

    def search(self, title: str) -> List[Dict]:
        """
        Look up a word, returning one entry per etymology (homograph).

        Unlike the media APIs this is an exact-word lookup, not a search: an
        unknown word yields no results rather than near misses.
        """
        word = title.strip()
        if not word:
            return []

        if self._primary_failed:
            entries = self._fetch_fallback(word)
        else:
            try:
                entries = self._fetch_primary(word)
            except requests.RequestException as e:
                # The community proxy is down or unreachable; fall back to
                # Wikimedia for this word and every later one in the batch
                print(f"⚠️  Dictionary API unavailable ({type(e).__name__}); "
                      "using Wiktionary")
                self._primary_failed = True
                entries = self._fetch_fallback(word)

        for entry in entries:
            self._entries[entry['id']] = entry

        return entries

    def _fetch_primary(self, word: str) -> List[Dict]:
        """Look the word up via the Free Dictionary API."""
        response = requests.get(
            f"{DICTIONARY_API_URL}/{quote(word)}",
            headers={'User-Agent': USER_AGENT},
            timeout=PRIMARY_TIMEOUT
        )

        # The word is genuinely absent from Wiktionary; the fallback shares that
        # data, so there is nothing to fall back to
        if response.status_code == 404:
            return []

        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, list):
            return []

        return [
            self._normalize_primary(word, index, entry)
            for index, entry in enumerate(payload)
        ]

    def _fetch_fallback(self, word: str) -> List[Dict]:
        """Look the word up via Wikimedia's Wiktionary REST endpoint."""
        try:
            response = requests.get(
                f"{WIKTIONARY_API_URL}/{quote(word)}",
                headers={'User-Agent': USER_AGENT},
                timeout=FALLBACK_TIMEOUT
            )

            if response.status_code == 404:
                return []

            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as e:
            raise Exception(f"Dictionary API error: {e}")

        # Keyed by language code; only English entries are wanted
        english = payload.get('en') if isinstance(payload, dict) else None
        if not english:
            return []

        return [self._normalize_fallback(word, english)]

    def _normalize_primary(self, word: str, index: int, entry: Dict) -> Dict:
        """Standardize one Free Dictionary API entry."""
        meanings = []
        synonyms: List[str] = []
        antonyms: List[str] = []

        for meaning in entry.get('meanings', []):
            definitions = []
            for definition in meaning.get('definitions', []):
                text = (definition.get('definition') or '').strip()
                if not text:
                    continue
                definitions.append({
                    'definition': text,
                    'example': (definition.get('example') or '').strip() or None,
                })
                self._collect(synonyms, definition.get('synonyms', []))
                self._collect(antonyms, definition.get('antonyms', []))

            self._collect(synonyms, meaning.get('synonyms', []))
            self._collect(antonyms, meaning.get('antonyms', []))

            if definitions:
                meanings.append({
                    'part_of_speech': meaning.get('partOfSpeech', 'definition'),
                    'definitions': definitions,
                })

        return {
            'id': f"{word}#{index}",
            'word': entry.get('word') or word,
            'phonetic': self._extract_phonetic(entry),
            'meanings': meanings,
            'synonyms': synonyms,
            'antonyms': antonyms,
            'source_urls': entry.get('sourceUrls', []),
            'license': (entry.get('license') or {}).get('name', WIKTIONARY_LICENSE),
            'source': 'dictionaryapi.dev',
        }

    def _normalize_fallback(self, word: str, sections: List[Dict]) -> Dict:
        """
        Standardize Wikimedia's response into the same shape as the primary.

        Wikimedia groups every part of speech under one entry rather than
        splitting homographs, so this always produces a single entry.
        """
        meanings = []

        for section in sections:
            definitions = []
            for definition in section.get('definitions', []):
                text = self._strip_html(definition.get('definition', '')).strip()
                if not text:
                    continue
                examples = [
                    self._strip_html(example).strip()
                    for example in definition.get('examples', [])
                ]
                definitions.append({
                    'definition': text,
                    'example': next((e for e in examples if e), None),
                })

            if definitions:
                meanings.append({
                    'part_of_speech': section.get('partOfSpeech', 'definition'),
                    'definitions': definitions,
                })

        return {
            'id': f"{word}#0",
            'word': word,
            'phonetic': None,
            'meanings': meanings,
            'synonyms': [],
            'antonyms': [],
            'source_urls': [f"https://en.wiktionary.org/wiki/{quote(word)}"],
            'license': WIKTIONARY_LICENSE,
            'source': 'wiktionary',
        }

    @staticmethod
    def _collect(target: List[str], values) -> None:
        """Append new, non-empty values to target, preserving order."""
        if not isinstance(values, list):
            return
        for value in values:
            value = str(value).strip()
            if value and value not in target:
                target.append(value)

    @staticmethod
    def _extract_phonetic(entry: Dict) -> Optional[str]:
        """Get the IPA transcription, which may sit in either of two fields."""
        phonetic = (entry.get('phonetic') or '').strip()
        if phonetic:
            return phonetic

        for candidate in entry.get('phonetics', []):
            text = (candidate.get('text') or '').strip()
            if text:
                return text

        return None

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove the HTML markup Wiktionary embeds in definition text."""
        return re.sub(r'<[^>]+>', '', text)

    def get_details(self, media_id: str) -> Dict:
        """Get the cached entry, looking the word up again if it is not cached."""
        if media_id in self._entries:
            return self._entries[media_id]

        # Called outside a search flow: re-fetch, then match on the synthetic id
        word = media_id.split('#')[0]
        for entry in self.search(word):
            if entry['id'] == media_id:
                return entry

        raise Exception(f"No dictionary entry found for '{media_id}'")

    def prompt_disambiguation(self, title: str, results: List[Dict]) -> Optional[Dict]:
        """Show entries and prompt user to select the correct one."""
        print(f"\n📖 Multiple entries found for '{title}':")
        print("-" * 80)

        for idx, result in enumerate(results, 1):
            meanings = result.get('meanings', [])
            parts = '/'.join(m.get('part_of_speech', '') for m in meanings if m)
            print(f"{idx}. {result.get('word', title)} [{parts or 'entry'}]")

            # One definition is enough to tell etymologies apart
            if meanings and meanings[0].get('definitions'):
                preview = meanings[0]['definitions'][0].get('definition', '')
                if len(preview) > 100:
                    preview = preview[:97] + '...'
                print(f"   {preview}")
            print()

        print("0. Skip this word")
        print("-" * 80)

        while True:
            try:
                choice = get_user_input("Select the correct match (0 to skip): ").strip()
                choice_num = int(choice)

                if choice_num == 0:
                    return None
                if 1 <= choice_num <= len(results):
                    return results[choice_num - 1]
                else:
                    print(f"Please enter a number between 0 and {len(results)}")
            except ValueError:
                print("Please enter a valid number")

    def format_note_content(self, details: Dict) -> str:
        """Generate markdown content for the note."""
        meanings = details.get('meanings', [])

        # Part of speech is the note's facet tag
        tags = []
        for meaning in meanings:
            tag = meaning.get('part_of_speech', '').lower().replace(' ', '-')
            if tag and tag not in tags:
                tags.append(tag)

        sections = []

        phonetic = details.get('phonetic')
        if phonetic:
            sections.append(f"## Pronunciation\n{phonetic}")

        for meaning in meanings:
            part_of_speech = meaning.get('part_of_speech') or 'Definition'
            lines = [f"## {part_of_speech.capitalize()}"]
            for idx, definition in enumerate(meaning.get('definitions', []), 1):
                lines.append(f"{idx}. {definition.get('definition', '')}")
                example = definition.get('example')
                if example:
                    lines.append(f"   - *{example}*")
            sections.append('\n'.join(lines))

        synonyms = details.get('synonyms', [])
        if synonyms:
            links = ', '.join(format_wikilink(word) for word in synonyms)
            sections.append(f"## Synonyms\n{links}")

        antonyms = details.get('antonyms', [])
        if antonyms:
            links = ', '.join(format_wikilink(word) for word in antonyms)
            sections.append(f"## Antonyms\n{links}")

        # CC BY-SA requires attribution, and these notes keep the text for good
        source_lines = list(details.get('source_urls', []))
        source_lines.append(details.get('license', WIKTIONARY_LICENSE))
        sections.append("## Source\n" + '\n'.join(source_lines))

        body = '\n\n'.join(sections)
        return f"{build_frontmatter('Lookups', tags)}\n\n{body}\n"

    def get_filename(self, details: Dict) -> str:
        """
        Generate filename in 'Word.md' format.

        Words have no release year, so the '(Year)' the media clients append
        would be meaningless here.
        """
        word = details.get('word', 'Unknown')
        return f"{sanitize_filename(word)}.md"

    def get_poster_url(self, details: Dict) -> Optional[str]:
        """Word lookups have no cover art."""
        return None
