"""Unit tests for lib/api/openlibrary_client.py"""

import json
import pytest
import responses

from lib.api.openlibrary_client import OpenLibraryClient


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def ol_client():
    """Create an Open Library client."""
    return OpenLibraryClient()


@pytest.fixture
def book_search_payload(api_responses_dir):
    with open(api_responses_dir / 'openlibrary_book_search.json') as f:
        return json.load(f)


@pytest.fixture
def book_work_payload(api_responses_dir):
    with open(api_responses_dir / 'openlibrary_book_work.json') as f:
        return json.load(f)


@pytest.fixture
def author_payload(api_responses_dir):
    with open(api_responses_dir / 'openlibrary_author.json') as f:
        return json.load(f)


# ============================================================================
# search()
# ============================================================================

@responses.activate
def test_search_success(ol_client, book_search_payload):
    responses.add(
        responses.GET,
        'https://openlibrary.org/search.json',
        json=book_search_payload,
        status=200,
    )

    results = ol_client.search('Dune')

    assert len(results) == 2
    assert results[0]['id'] == 'OL893415W'
    assert results[0]['title'] == 'Dune'
    assert results[0]['author'] == 'Frank Herbert'
    assert results[0]['first_publish_year'] == 1965
    assert results[0]['cover_id'] == 8739161
    assert 'Science fiction' in results[0]['subjects']


@responses.activate
def test_search_no_results(ol_client):
    responses.add(
        responses.GET,
        'https://openlibrary.org/search.json',
        json={'numFound': 0, 'docs': []},
        status=200,
    )

    results = ol_client.search('zzzzzzzzz_no_such_book')

    assert results == []


@responses.activate
def test_search_multiple_authors_joined(ol_client):
    responses.add(
        responses.GET,
        'https://openlibrary.org/search.json',
        json={'docs': [{
            'key': '/works/OL1W',
            'title': 'Collab',
            'author_name': ['Alice', 'Bob', 'Carol'],
            'first_publish_year': 2020,
        }]},
        status=200,
    )

    results = ol_client.search('Collab')

    assert results[0]['author'] == 'Alice & Bob & Carol'


@responses.activate
def test_search_missing_author_defaults_to_unknown(ol_client):
    responses.add(
        responses.GET,
        'https://openlibrary.org/search.json',
        json={'docs': [{
            'key': '/works/OL1W',
            'title': 'Anonymous Book',
            'first_publish_year': 1800,
        }]},
        status=200,
    )

    results = ol_client.search('Anonymous Book')

    assert results[0]['author'] == 'Unknown'


@responses.activate
def test_search_caps_subjects_to_five(ol_client):
    responses.add(
        responses.GET,
        'https://openlibrary.org/search.json',
        json={'docs': [{
            'key': '/works/OL1W',
            'title': 'Tagged Book',
            'author_name': ['Author'],
            'first_publish_year': 2000,
            'subject': [f'subject-{i}' for i in range(20)],
        }]},
        status=200,
    )

    results = ol_client.search('Tagged Book')

    assert len(results[0]['subjects']) == 5


@responses.activate
def test_search_http_error_raises(ol_client):
    responses.add(
        responses.GET,
        'https://openlibrary.org/search.json',
        json={'error': 'server'},
        status=500,
    )

    with pytest.raises(Exception) as excinfo:
        ol_client.search('Dune')

    assert 'Open Library API error' in str(excinfo.value)


# ============================================================================
# get_details()
# ============================================================================

@responses.activate
def test_get_details_success(ol_client, book_work_payload, author_payload):
    responses.add(
        responses.GET,
        'https://openlibrary.org/works/OL893415W.json',
        json=book_work_payload,
        status=200,
    )
    responses.add(
        responses.GET,
        'https://openlibrary.org/authors/OL233422A.json',
        json=author_payload,
        status=200,
    )

    details = ol_client.get_details('OL893415W')

    assert details['id'] == 'OL893415W'
    assert details['title'] == 'Dune'
    assert details['author'] == 'Frank Herbert'
    assert 'desert planet' in details['description']
    assert details['cover_id'] == 8739161
    assert details['first_publish_year'] == 1965
    assert 'Science fiction' in details['subjects']


@responses.activate
def test_get_details_description_as_dict(ol_client, author_payload):
    """Open Library sometimes wraps description in {'type': ..., 'value': ...}."""
    work_payload = {
        'title': 'Book',
        'authors': [{'author': {'key': '/authors/OL233422A'}}],
        'description': {'type': '/type/text', 'value': 'Wrapped description.'},
        'covers': [42],
        'subjects': [],
        'first_publish_date': '2001',
    }
    responses.add(
        responses.GET,
        'https://openlibrary.org/works/OL1W.json',
        json=work_payload,
        status=200,
    )
    responses.add(
        responses.GET,
        'https://openlibrary.org/authors/OL233422A.json',
        json=author_payload,
        status=200,
    )

    details = ol_client.get_details('OL1W')

    assert details['description'] == 'Wrapped description.'


@responses.activate
def test_get_details_falls_back_to_editions_for_year(ol_client, author_payload):
    """When the work has no first_publish_date, fetch editions to find earliest year."""
    work_payload = {
        'title': 'No Date Book',
        'authors': [{'author': {'key': '/authors/OL233422A'}}],
        'covers': [99],
        'subjects': [],
    }
    editions_payload = {
        'entries': [
            {'publish_date': 'September 2005'},
            {'publish_date': '1999'},
            {'publish_date': '2010-03-15'},
        ]
    }
    responses.add(
        responses.GET,
        'https://openlibrary.org/works/OL1W.json',
        json=work_payload,
        status=200,
    )
    responses.add(
        responses.GET,
        'https://openlibrary.org/authors/OL233422A.json',
        json=author_payload,
        status=200,
    )
    responses.add(
        responses.GET,
        'https://openlibrary.org/works/OL1W/editions.json',
        json=editions_payload,
        status=200,
    )

    details = ol_client.get_details('OL1W')

    assert details['first_publish_year'] == 1999


@responses.activate
def test_get_details_no_year_anywhere(ol_client, author_payload):
    work_payload = {
        'title': 'Mystery',
        'authors': [{'author': {'key': '/authors/OL233422A'}}],
        'covers': [],
        'subjects': [],
    }
    responses.add(
        responses.GET,
        'https://openlibrary.org/works/OL1W.json',
        json=work_payload,
        status=200,
    )
    responses.add(
        responses.GET,
        'https://openlibrary.org/authors/OL233422A.json',
        json=author_payload,
        status=200,
    )
    responses.add(
        responses.GET,
        'https://openlibrary.org/works/OL1W/editions.json',
        json={'entries': []},
        status=200,
    )

    details = ol_client.get_details('OL1W')

    assert details['first_publish_year'] is None
    assert details['cover_id'] is None


@responses.activate
def test_get_details_no_authors(ol_client):
    work_payload = {
        'title': 'Anonymous Work',
        'description': 'No author info.',
        'covers': [1],
        'subjects': [],
        'first_publish_date': '1850',
    }
    responses.add(
        responses.GET,
        'https://openlibrary.org/works/OL1W.json',
        json=work_payload,
        status=200,
    )

    details = ol_client.get_details('OL1W')

    assert details['author'] == 'Unknown'


@responses.activate
def test_get_details_author_lookup_failure_skipped(ol_client):
    """If an author lookup fails, other authors are still returned."""
    work_payload = {
        'title': 'Co-authored',
        'authors': [
            {'author': {'key': '/authors/OL_GOOD'}},
            {'author': {'key': '/authors/OL_BAD'}},
        ],
        'covers': [],
        'subjects': [],
        'first_publish_date': '2000',
    }
    responses.add(
        responses.GET,
        'https://openlibrary.org/works/OL1W.json',
        json=work_payload,
        status=200,
    )
    responses.add(
        responses.GET,
        'https://openlibrary.org/authors/OL_GOOD.json',
        json={'name': 'Good Author'},
        status=200,
    )
    responses.add(
        responses.GET,
        'https://openlibrary.org/authors/OL_BAD.json',
        json={'error': 'oops'},
        status=500,
    )

    details = ol_client.get_details('OL1W')

    assert details['author'] == 'Good Author'


@responses.activate
def test_get_details_http_error_raises(ol_client):
    responses.add(
        responses.GET,
        'https://openlibrary.org/works/OL1W.json',
        json={'error': 'server'},
        status=500,
    )

    with pytest.raises(Exception) as excinfo:
        ol_client.get_details('OL1W')

    assert 'Open Library API error' in str(excinfo.value)


# ============================================================================
# format_note_content()
# ============================================================================

def test_format_note_content_full(ol_client):
    details = {
        'id': 'OL893415W',
        'title': 'Dune',
        'author': 'Frank Herbert',
        'description': 'A desert planet.',
        'cover_id': 8739161,
        'subjects': ['Science fiction'],
        'first_publish_year': 1965,
    }

    content = ol_client.format_note_content(details)

    assert content.startswith('---')
    assert '  - book' in content
    assert '## Links' in content
    assert 'openlibrary.org/works/OL893415W' in content
    assert '## Description' in content
    assert 'A desert planet.' in content
    assert 'By [[Frank Herbert]].' in content


def test_format_note_content_no_description(ol_client):
    details = {
        'id': 'OL1W',
        'title': 'Bare Book',
        'author': 'Author',
        'description': '',
        'cover_id': None,
        'subjects': [],
        'first_publish_year': 2000,
    }

    content = ol_client.format_note_content(details)

    # Description section exists but contains only the author byline
    assert 'By [[Author]].' in content
    # Should not double-print the description
    assert content.count('## Description') == 1


def test_format_note_content_no_id_renders_not_available(ol_client):
    details = {
        'title': 'Anon',
        'author': 'A',
        'description': 'd',
        'subjects': [],
        'first_publish_year': 1900,
    }

    content = ol_client.format_note_content(details)

    assert 'Not available' in content


# ============================================================================
# get_filename()
# ============================================================================

def test_get_filename_basic(ol_client):
    details = {
        'author': 'Frank Herbert',
        'title': 'Dune',
        'first_publish_year': 1965,
    }

    assert ol_client.get_filename(details) == 'Frank Herbert - Dune (1965).md'


def test_get_filename_missing_year_uses_tbd(ol_client):
    details = {
        'author': 'Author',
        'title': 'Unknown Year Book',
        'first_publish_year': None,
    }

    assert ol_client.get_filename(details) == 'Author - Unknown Year Book (TBD).md'


def test_get_filename_sanitizes_special_characters(ol_client):
    details = {
        'author': 'A/B:C',
        'title': 'Title: Subtitle?',
        'first_publish_year': 1999,
    }

    filename = ol_client.get_filename(details)

    # Colons turn into ' -', slashes into '-', '?' stripped
    assert filename == 'A-B -C - Title - Subtitle (1999).md'


def test_get_filename_multiple_authors(ol_client):
    details = {
        'author': 'Alice & Bob',
        'title': 'Joint Work',
        'first_publish_year': 2020,
    }

    assert ol_client.get_filename(details) == 'Alice & Bob - Joint Work (2020).md'


# ============================================================================
# get_poster_url()
# ============================================================================

def test_get_poster_url(ol_client):
    details = {'cover_id': 8739161}

    url = ol_client.get_poster_url(details)

    assert url == 'https://covers.openlibrary.org/b/id/8739161-L.jpg'


def test_get_poster_url_missing(ol_client):
    assert ol_client.get_poster_url({}) is None


def test_get_poster_url_none(ol_client):
    assert ol_client.get_poster_url({'cover_id': None}) is None


# ============================================================================
# prompt_disambiguation()
# ============================================================================

def test_prompt_disambiguation_select(ol_client, mocker):
    results = [
        {'title': 'Dune', 'author': 'Frank Herbert', 'first_publish_year': 1965},
        {'title': 'Dune Messiah', 'author': 'Frank Herbert', 'first_publish_year': 1969},
    ]

    inputs = iter(['2'])
    mocker.patch('lib.api.openlibrary_client.get_user_input', lambda prompt: next(inputs))

    selected = ol_client.prompt_disambiguation('Dune', results)

    assert selected['title'] == 'Dune Messiah'


def test_prompt_disambiguation_skip(ol_client, mocker):
    results = [{'title': 'Dune', 'author': 'Frank Herbert', 'first_publish_year': 1965}]

    inputs = iter(['0'])
    mocker.patch('lib.api.openlibrary_client.get_user_input', lambda prompt: next(inputs))

    assert ol_client.prompt_disambiguation('Dune', results) is None


def test_prompt_disambiguation_invalid_then_valid(ol_client, mocker, capsys):
    results = [{'title': 'Dune', 'author': 'Frank Herbert', 'first_publish_year': 1965}]

    inputs = iter(['99', 'abc', '1'])
    mocker.patch('lib.api.openlibrary_client.get_user_input', lambda prompt: next(inputs))

    selected = ol_client.prompt_disambiguation('Dune', results)

    assert selected is not None
    captured = capsys.readouterr()
    assert 'between 0 and 1' in captured.out
    assert 'valid number' in captured.out


def test_prompt_disambiguation_displays_tbd_for_missing_year(ol_client, mocker, capsys):
    results = [{'title': 'Future Book', 'author': 'A', 'first_publish_year': None}]

    inputs = iter(['1'])
    mocker.patch('lib.api.openlibrary_client.get_user_input', lambda prompt: next(inputs))

    ol_client.prompt_disambiguation('Future Book', results)

    captured = capsys.readouterr()
    assert '(TBD)' in captured.out
