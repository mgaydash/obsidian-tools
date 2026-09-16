"""Unit tests for lib/api/dictionary_client.py"""

import json

import pytest
import requests
import responses

from lib.api.dictionary_client import (
    DICTIONARY_API_URL,
    WIKTIONARY_API_URL,
    DictionaryClient,
)

# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def dict_client():
    """Create a dictionary client."""
    return DictionaryClient()


@pytest.fixture
def entry_response(api_responses_dir):
    """Load a single-entry Free Dictionary API response."""
    with open(api_responses_dir / 'dictionary_entry.json') as f:
        return json.load(f)


@pytest.fixture
def homograph_response(api_responses_dir):
    """Load a two-entry (homograph) Free Dictionary API response."""
    with open(api_responses_dir / 'dictionary_homographs.json') as f:
        return json.load(f)


@pytest.fixture
def wiktionary_response(api_responses_dir):
    """Load a Wikimedia Wiktionary REST response."""
    with open(api_responses_dir / 'wiktionary_definition.json') as f:
        return json.load(f)


@pytest.fixture
def serendipity_details(dict_client, entry_response):
    """
    A normalized entry, as search() would produce it.

    Built straight from the fixture rather than through search(): pytest
    resolves fixtures before @responses.activate takes effect, so any HTTP here
    would escape the mock and hit the real API.
    """
    return dict_client._normalize_primary('serendipity', 0, entry_response[0])


# ============================================================================
# Tests for search - primary source
# ============================================================================

@responses.activate
def test_search_returns_normalized_entry(dict_client, entry_response):
    """Test that search standardizes the Free Dictionary response."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/serendipity',
        json=entry_response,
        status=200
    )

    results = dict_client.search('serendipity')

    assert len(results) == 1
    assert results[0]['word'] == 'serendipity'
    assert results[0]['id'] == 'serendipity#0'
    assert results[0]['phonetic'] == '/ˌsɛ.ɹən.ˈdɪ.pɪ.ti/'
    assert results[0]['source'] == 'dictionaryapi.dev'
    assert results[0]['license'] == 'CC BY-SA 3.0'
    assert results[0]['source_urls'] == ['https://en.wiktionary.org/wiki/serendipity']


@responses.activate
def test_search_collects_definitions_and_examples(dict_client, entry_response):
    """Test that definitions keep their text and optional example."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/serendipity',
        json=entry_response,
        status=200
    )

    meanings = dict_client.search('serendipity')[0]['meanings']

    assert len(meanings) == 1
    assert meanings[0]['part_of_speech'] == 'noun'
    assert len(meanings[0]['definitions']) == 2
    assert meanings[0]['definitions'][0]['example'] is None
    assert meanings[0]['definitions'][1]['example'] == (
        'The discovery of penicillin was pure serendipity.'
    )


@responses.activate
def test_search_deduplicates_synonyms_and_antonyms(dict_client, entry_response):
    """Test that synonyms repeated at definition and meaning level appear once."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/serendipity',
        json=entry_response,
        status=200
    )

    entry = dict_client.search('serendipity')[0]

    assert entry['synonyms'] == ['chance', 'luck']
    assert entry['antonyms'] == ["Murphy's law", 'perfect storm']


@responses.activate
def test_search_returns_one_entry_per_homograph(dict_client, homograph_response):
    """Test that each etymology becomes its own selectable entry."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/bass',
        json=homograph_response,
        status=200
    )

    results = dict_client.search('bass')

    assert len(results) == 2
    assert [r['id'] for r in results] == ['bass#0', 'bass#1']
    assert results[0]['phonetic'] == '/beɪs/'
    assert results[1]['phonetic'] == '/bæs/'


@responses.activate
def test_search_unknown_word_returns_empty(dict_client):
    """Test that a 404 yields no results rather than raising."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/qwertyuiop',
        json={'title': 'No Definitions Found'},
        status=404
    )

    assert dict_client.search('qwertyuiop') == []


def test_search_empty_string_makes_no_request(dict_client):
    """Test that a blank word short-circuits before any HTTP call."""
    assert dict_client.search('   ') == []


@responses.activate
def test_search_ignores_unexpected_payload_shape(dict_client):
    """Test that a non-list payload is treated as no results."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/odd',
        json={'title': 'Something else'},
        status=200
    )

    assert dict_client.search('odd') == []


@responses.activate
def test_search_url_encodes_the_word(dict_client, entry_response):
    """Test that multi-word lookups are encoded into the path."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/ad%20hoc',
        json=entry_response,
        status=200
    )

    dict_client.search('ad hoc')

    assert '%20' in responses.calls[0].request.url


@responses.activate
def test_search_falls_back_to_phonetics_array(dict_client):
    """Test that IPA is read from phonetics[] when 'phonetic' is absent."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/test',
        json=[{
            'word': 'test',
            'phonetics': [{'audio': 'x.mp3'}, {'text': '/tɛst/'}],
            'meanings': [{'partOfSpeech': 'noun', 'definitions': [{'definition': 'A trial.'}]}]
        }],
        status=200
    )

    assert dict_client.search('test')[0]['phonetic'] == '/tɛst/'


@responses.activate
def test_search_entry_without_phonetic_is_none(dict_client):
    """Test that a missing IPA yields None rather than an empty string."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/test',
        json=[{
            'word': 'test',
            'meanings': [{'partOfSpeech': 'noun', 'definitions': [{'definition': 'A trial.'}]}]
        }],
        status=200
    )

    assert dict_client.search('test')[0]['phonetic'] is None


@responses.activate
def test_search_drops_meanings_with_no_usable_definitions(dict_client):
    """Test that empty definition text does not produce an empty section."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/test',
        json=[{
            'word': 'test',
            'meanings': [
                {'partOfSpeech': 'noun', 'definitions': [{'definition': '   '}]},
                {'partOfSpeech': 'verb', 'definitions': [{'definition': 'To try.'}]}
            ]
        }],
        status=200
    )

    meanings = dict_client.search('test')[0]['meanings']

    assert len(meanings) == 1
    assert meanings[0]['part_of_speech'] == 'verb'


# ============================================================================
# Tests for search - Wiktionary fallback
# ============================================================================

@responses.activate
def test_search_falls_back_when_primary_errors(dict_client, wiktionary_response):
    """Test that a 5xx from the community proxy falls back to Wikimedia."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/serendipity',
        body='upstream down',
        status=522
    )
    responses.add(
        responses.GET,
        f'{WIKTIONARY_API_URL}/serendipity',
        json=wiktionary_response,
        status=200
    )

    results = dict_client.search('serendipity')

    assert len(results) == 1
    assert results[0]['source'] == 'wiktionary'
    assert results[0]['id'] == 'serendipity#0'


@responses.activate
def test_search_falls_back_on_connection_error(dict_client, wiktionary_response):
    """Test that an unreachable primary host falls back rather than raising."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/serendipity',
        body=requests.ConnectionError('no route to host')
    )
    responses.add(
        responses.GET,
        f'{WIKTIONARY_API_URL}/serendipity',
        json=wiktionary_response,
        status=200
    )

    assert dict_client.search('serendipity')[0]['source'] == 'wiktionary'


@responses.activate
def test_fallback_strips_html_from_definitions(dict_client, wiktionary_response):
    """Test that Wiktionary's embedded markup is removed."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/serendipity',
        body='down',
        status=522
    )
    responses.add(
        responses.GET,
        f'{WIKTIONARY_API_URL}/serendipity',
        json=wiktionary_response,
        status=200
    )

    definitions = dict_client.search('serendipity')[0]['meanings'][0]['definitions']

    assert '<a' not in definitions[0]['definition']
    assert definitions[0]['definition'].startswith('The phenomenon of finding')
    assert definitions[0]['example'] == 'A fortunate stroke of serendipity.'


@responses.activate
def test_fallback_uses_only_english_sections(dict_client, wiktionary_response):
    """Test that non-English Wiktionary sections are ignored."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/serendipity',
        body='down',
        status=522
    )
    responses.add(
        responses.GET,
        f'{WIKTIONARY_API_URL}/serendipity',
        json=wiktionary_response,
        status=200
    )

    entry = dict_client.search('serendipity')[0]

    assert len(entry['meanings']) == 1
    assert entry['meanings'][0]['part_of_speech'] == 'Noun'


@responses.activate
def test_fallback_404_returns_empty(dict_client):
    """Test that a word missing from both sources yields no results."""
    responses.add(responses.GET, f'{DICTIONARY_API_URL}/qwertyuiop', body='down', status=522)
    responses.add(responses.GET, f'{WIKTIONARY_API_URL}/qwertyuiop', json={}, status=404)

    assert dict_client.search('qwertyuiop') == []


@responses.activate
def test_fallback_without_english_returns_empty(dict_client):
    """Test that a response with no 'en' key yields no results."""
    responses.add(responses.GET, f'{DICTIONARY_API_URL}/mot', body='down', status=522)
    responses.add(
        responses.GET,
        f'{WIKTIONARY_API_URL}/mot',
        json={'fr': [{'partOfSpeech': 'Noun', 'definitions': [{'definition': 'word'}]}]},
        status=200
    )

    assert dict_client.search('mot') == []


@responses.activate
def test_both_sources_down_raises(dict_client):
    """Test that losing both sources surfaces an error to the caller."""
    responses.add(responses.GET, f'{DICTIONARY_API_URL}/serendipity', body='down', status=522)
    responses.add(responses.GET, f'{WIKTIONARY_API_URL}/serendipity', body='down', status=503)

    with pytest.raises(Exception, match='Dictionary API error'):
        dict_client.search('serendipity')


# ============================================================================
# Tests for get_details
# ============================================================================

@responses.activate
def test_get_details_uses_cached_entry(dict_client, entry_response):
    """Test that details come from the search response, with no second request."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/serendipity',
        json=entry_response,
        status=200
    )

    dict_client.search('serendipity')
    details = dict_client.get_details('serendipity#0')

    assert details['word'] == 'serendipity'
    assert len(responses.calls) == 1


@responses.activate
def test_get_details_refetches_when_not_cached(dict_client, entry_response):
    """Test that an uncached id triggers a fresh lookup."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/serendipity',
        json=entry_response,
        status=200
    )

    details = dict_client.get_details('serendipity#0')

    assert details['word'] == 'serendipity'
    assert len(responses.calls) == 1


@responses.activate
def test_get_details_unknown_id_raises(dict_client, entry_response):
    """Test that an id with no matching entry raises."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/serendipity',
        json=entry_response,
        status=200
    )

    with pytest.raises(Exception, match='No dictionary entry found'):
        dict_client.get_details('serendipity#7')


# ============================================================================
# Tests for format_note_content
# ============================================================================

def test_format_note_content_declares_collection(dict_client, serendipity_details):
    """Test that notes carry the Lookups collection."""
    content = dict_client.format_note_content(serendipity_details)

    assert content.startswith('---\ncollection: "[[Lookups]]"\n')


def test_format_note_content_tags_part_of_speech(dict_client, serendipity_details):
    """Test that part of speech becomes a facet tag."""
    content = dict_client.format_note_content(serendipity_details)

    assert 'tags:\n  - noun\n' in content


def test_format_note_content_numbers_definitions(dict_client, serendipity_details):
    """Test that each sense is a numbered list item under its part of speech."""
    content = dict_client.format_note_content(serendipity_details)

    assert '## Noun' in content
    assert '1. A combination of events' in content
    assert '2. An unsought, unintended' in content


def test_format_note_content_includes_example(dict_client, serendipity_details):
    """Test that an example is rendered under its definition."""
    content = dict_client.format_note_content(serendipity_details)

    assert '   - *The discovery of penicillin was pure serendipity.*' in content


def test_format_note_content_links_synonyms(dict_client, serendipity_details):
    """Test that synonyms and antonyms become wikilinks."""
    content = dict_client.format_note_content(serendipity_details)

    assert '## Synonyms\n[[chance]], [[luck]]' in content
    assert "## Antonyms\n[[Murphy's law]], [[perfect storm]]" in content


def test_format_note_content_attributes_source(dict_client, serendipity_details):
    """Test that the CC BY-SA source and license are recorded in the note."""
    content = dict_client.format_note_content(serendipity_details)

    assert '## Source\nhttps://en.wiktionary.org/wiki/serendipity\nCC BY-SA 3.0' in content


def test_format_note_content_omits_empty_sections(dict_client):
    """Test that absent pronunciation and synonyms leave no empty headings."""
    details = {
        'word': 'test',
        'phonetic': None,
        'meanings': [{'part_of_speech': 'noun', 'definitions': [{'definition': 'A trial.'}]}],
        'synonyms': [],
        'antonyms': [],
        'source_urls': ['https://en.wiktionary.org/wiki/test'],
        'license': 'CC BY-SA 3.0',
    }

    content = dict_client.format_note_content(details)

    assert '## Pronunciation' not in content
    assert '## Synonyms' not in content
    assert '## Antonyms' not in content


def test_format_note_content_omits_tags_key_without_meanings(dict_client):
    """Test that a note with no part of speech carries no tags key."""
    details = {
        'word': 'test',
        'meanings': [],
        'source_urls': ['https://en.wiktionary.org/wiki/test'],
        'license': 'CC BY-SA 3.0',
    }

    content = dict_client.format_note_content(details)

    assert 'tags:' not in content
    assert 'collection: "[[Lookups]]"' in content


def test_format_note_content_hyphenates_multiword_part_of_speech(dict_client):
    """Test that 'phrasal verb' becomes a single hyphenated tag."""
    details = {
        'word': 'give up',
        'meanings': [
            {'part_of_speech': 'phrasal verb', 'definitions': [{'definition': 'To quit.'}]}
        ],
        'source_urls': [],
        'license': 'CC BY-SA 3.0',
    }

    content = dict_client.format_note_content(details)

    assert '  - phrasal-verb\n' in content
    assert '## Phrasal verb' in content


# ============================================================================
# Tests for get_filename
# ============================================================================

def test_get_filename_omits_year(dict_client):
    """Test that lookup filenames are just the word."""
    assert dict_client.get_filename({'word': 'serendipity'}) == 'serendipity.md'


def test_get_filename_sanitizes_word(dict_client):
    """Test that filesystem-hostile characters are replaced."""
    assert dict_client.get_filename({'word': 'and/or'}) == 'and-or.md'


def test_get_filename_missing_word(dict_client):
    """Test the fallback when an entry somehow has no word."""
    assert dict_client.get_filename({}) == 'Unknown.md'


# ============================================================================
# Tests for get_poster_url
# ============================================================================

def test_get_poster_url_always_none(dict_client):
    """Test that word lookups never report cover art."""
    assert dict_client.get_poster_url({'word': 'serendipity'}) is None


# ============================================================================
# Tests for prompt_disambiguation
# ============================================================================

@responses.activate
def test_prompt_disambiguation_selects_entry(dict_client, homograph_response, mocker):
    """Test that the user's choice returns the matching entry."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/bass',
        json=homograph_response,
        status=200
    )
    results = dict_client.search('bass')
    mocker.patch('lib.api.dictionary_client.get_user_input', return_value='2')

    assert dict_client.prompt_disambiguation('bass', results)['id'] == 'bass#1'


@responses.activate
def test_prompt_disambiguation_skip(dict_client, homograph_response, mocker):
    """Test that 0 skips the word."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/bass',
        json=homograph_response,
        status=200
    )
    results = dict_client.search('bass')
    mocker.patch('lib.api.dictionary_client.get_user_input', return_value='0')

    assert dict_client.prompt_disambiguation('bass', results) is None


@responses.activate
def test_prompt_disambiguation_reprompts_on_bad_input(dict_client, homograph_response, mocker):
    """Test that non-numeric and out-of-range input re-prompts."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/bass',
        json=homograph_response,
        status=200
    )
    results = dict_client.search('bass')
    mocker.patch(
        'lib.api.dictionary_client.get_user_input',
        side_effect=['abc', '9', '1']
    )

    assert dict_client.prompt_disambiguation('bass', results)['id'] == 'bass#0'


@responses.activate
def test_prompt_disambiguation_truncates_long_preview(dict_client, capsys, mocker):
    """Test that a long definition is shortened in the selection list."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/test',
        json=[{
            'word': 'test',
            'meanings': [{
                'partOfSpeech': 'noun',
                'definitions': [{'definition': 'A ' + 'very ' * 40 + 'long definition.'}]
            }]
        }, {
            'word': 'test',
            'meanings': [{'partOfSpeech': 'verb', 'definitions': [{'definition': 'To try.'}]}]
        }],
        status=200
    )
    results = dict_client.search('test')
    mocker.patch('lib.api.dictionary_client.get_user_input', return_value='1')

    dict_client.prompt_disambiguation('test', results)

    assert '...' in capsys.readouterr().out


# ============================================================================
# Tests for the primary-source circuit breaker
# ============================================================================

@responses.activate
def test_primary_failure_short_circuits_rest_of_batch(dict_client, wiktionary_response):
    """Test that a failed primary is not retried for later words in the run."""
    responses.add(responses.GET, f'{DICTIONARY_API_URL}/first', body='down', status=522)
    responses.add(responses.GET, f'{WIKTIONARY_API_URL}/first', json=wiktionary_response)
    responses.add(responses.GET, f'{WIKTIONARY_API_URL}/second', json=wiktionary_response)

    dict_client.search('first')
    dict_client.search('second')

    # 2 primary attempts would mean the breaker never tripped
    primary_calls = [c for c in responses.calls if DICTIONARY_API_URL in c.request.url]
    assert len(primary_calls) == 1
    assert dict_client._primary_failed is True


@responses.activate
def test_primary_success_leaves_breaker_closed(dict_client, entry_response):
    """Test that a healthy primary keeps serving every word."""
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/serendipity',
        json=entry_response,
        status=200
    )

    dict_client.search('serendipity')

    assert dict_client._primary_failed is False


@responses.activate
def test_primary_404_does_not_trip_breaker(dict_client, entry_response):
    """Test that an unknown word is not mistaken for an outage."""
    responses.add(responses.GET, f'{DICTIONARY_API_URL}/qwertyuiop', json={}, status=404)
    responses.add(
        responses.GET,
        f'{DICTIONARY_API_URL}/serendipity',
        json=entry_response,
        status=200
    )

    assert dict_client.search('qwertyuiop') == []
    assert dict_client.search('serendipity')[0]['source'] == 'dictionaryapi.dev'
    assert dict_client._primary_failed is False
