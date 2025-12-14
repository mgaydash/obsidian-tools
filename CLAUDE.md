# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python-based CLI tool for managing media notes (movies, TV shows, games) in Obsidian vaults. Uses TMDB API for movies/TV and IGDB API for games to fetch metadata, create notes, and download posters.

## Architecture

### Code Structure

```
lib/                              # Shared library modules
├── api/                          # API client implementations
│   ├── __init__.py              # MediaAPIFactory for routing
│   ├── base.py                  # Abstract MediaAPIClient interface
│   ├── tmdb_client.py           # TMDB implementation (movies/TV)
│   └── igdb_client.py           # IGDB implementation (games)
├── backup.py                    # Vault backup utilities
├── obsidian_utils.py            # YAML, wikilinks, year extraction, disambiguation
└── poster_downloader.py         # Poster download and frontmatter updates

obsidian_media_add.py            # Main CLI with subcommands
```

### Key Design Patterns

**Factory Pattern (`lib/api/__init__.py`):**
- `MediaAPIFactory.create_client(media_type)` routes to appropriate API client
- Returns TMDB client for 'movie'/'tv', IGDB client for 'game'
- Validates environment variables (TMDB_API_KEY, IGDB_CLIENT_ID, IGDB_ACCESS_TOKEN)

**Abstract Base Class (`lib/api/base.py`):**
All API clients implement `MediaAPIClient` interface:
- `search(title)` - Search API for title
- `get_details(media_id)` - Fetch full details
- `prompt_disambiguation(title, results)` - Interactive selection
- `format_note_content(details)` - Generate markdown
- `get_filename(details)` - Generate "Title (Year).md" filename

**Shared Disambiguation Logic (`lib/obsidian_utils.py`):**
- `extract_title_and_year(input)` - Extracts year from "Title (Year)" format
- `filter_results_by_year(results, year, media_type)` - Filters API results by year
- `find_exact_title_match(results, title, media_type)` - Auto-selects exact matches

This shared logic ensures consistent behavior across both 'add' and 'posters' commands.

## Commands

### Setup
```bash
pip install -r requirements.txt

# Set environment variables
export TMDB_API_KEY='your_key'           # For movies/TV
export IGDB_CLIENT_ID='your_client_id'   # For games
export IGDB_ACCESS_TOKEN='your_token'    # For games
```

### Main CLI Commands

**Add new media notes:**
```bash
# Movies (reads from stdin, newline-separated)
echo -e "Inception\nThe Matrix" | python obsidian_media_add.py add ~/vault backup.zip --media-type movie

# TV shows
python obsidian_media_add.py add ~/vault backup.zip --media-type tv
# Then paste titles and press Ctrl+D

# Games
echo "Elden Ring" | python obsidian_media_add.py add ~/vault backup.zip --media-type game
```

**Download posters for existing notes:**
```bash
# Default 200px width
python obsidian_media_add.py posters ~/vault backup.zip

# Custom width
python obsidian_media_add.py posters ~/vault backup.zip --width 300
```

### Check syntax
```bash
python3 -m py_compile obsidian_media_add.py lib/*.py lib/api/*.py
```

## Important Implementation Details

### Year-Based Auto-Disambiguation

Both 'add' and 'posters' commands use intelligent disambiguation:

1. Extract year from input: "Inception (2010)" → title="Inception", year="2010"
2. Search API with title only (without year)
3. Filter results by year if provided
4. Check for exact title match (case-insensitive)
5. If exact match found → auto-select
6. Else if multiple results → prompt user
7. Else if single result → auto-select

**Example:** "Loot (2022)" automatically selects "Loot" over "Loot - Blood Treasure" due to exact title match.

### API Response Formats

**TMDB (movies/TV):**
- Movies use 'title' and 'release_date'
- TV uses 'name' and 'first_air_date'
- Both return 'credits' (cast/crew) and 'external_ids' (IMDB)

**IGDB (games):**
- Uses 'name' and 'first_release_date' (Unix timestamp)
- Returns 'involved_companies' with developer/publisher flags
- Returns 'url' instead of external_ids

### Tag Detection

Scripts search for 'movie' or 'series' tags in:
1. YAML frontmatter: `tags: [movie]`
2. Hashtag format: `#movie`

Note: Avoids 'entertainment' tag (deprecated).

### Poster Download Workflow

1. Scan vault for files tagged 'movie' or 'series' without 'poster' property
2. Extract title and year from filename
3. Search TMDB (converts 'series' → 'tv' for API)
4. Download poster, resize maintaining aspect ratio
5. Convert to JPEG (quality=85)
6. Save as "Title (Year).jpg"
7. Update YAML frontmatter: `poster: [[filename.jpg]]`

### Wikilink Formatting

- Cast: `Character ([[Actor Name]])`
- Director/Creator: `[[Name]]`
- Poster: `poster: [[filename.jpg]]` (in YAML, not embedded)

### Filename Sanitization

Replaces problematic characters:
- `:` → ` -`
- `/` and `\` → `-`

Applied to all generated filenames.

## Environment Variables

**Required for movies/TV:**
- `TMDB_API_KEY` - Get from https://www.themoviedb.org/ (Settings > API)

**Required for games:**
- `IGDB_CLIENT_ID` - Twitch application client ID
- `IGDB_ACCESS_TOKEN` - Twitch OAuth access token
- Setup: https://api-docs.igdb.com/#getting-started

## Common Patterns

### Adding New Subcommands

1. Create handler function in `obsidian_media_add.py`: `def handle_<name>_command(args):`
2. Add subparser in `main()`:
   ```python
   parser = subparsers.add_parser('<name>', help='...')
   parser.add_argument(...)
   ```
3. Route in main: `if args.command == '<name>': handle_<name>_command(args)`

### Adding New API Clients

1. Create client in `lib/api/<name>_client.py`
2. Implement `MediaAPIClient` abstract methods
3. Add to factory in `lib/api/__init__.py`
4. Update `media_type` choices in CLI arguments

### Extending Disambiguation Logic

Shared logic in `lib/obsidian_utils.py` used by all commands. Modify `find_exact_title_match()` or `filter_results_by_year()` to affect both 'add' and 'posters' commands simultaneously.
