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
├── poster_utils.py              # Shared poster download/resize utilities
└── poster_downloader.py         # Standalone poster command implementation

obsidian_media_add.py            # Main CLI with subcommands
```

### Key Design Patterns

**Factory Pattern (`lib/api/__init__.py`):**
- `MediaAPIFactory.create_client(media_type)` routes to appropriate API client
- Returns TMDB client for 'movie'/'tv', IGDB client for 'game'
- Validates environment variables (TMDB_API_KEY, IGDB_CLIENT_ID, IGDB_CLIENT_SECRET)

**Abstract Base Class (`lib/api/base.py`):**
All API clients implement `MediaAPIClient` interface:
- `search(title)` - Search API for title
- `get_details(media_id)` - Fetch full details
- `prompt_disambiguation(title, results)` - Interactive selection
- `format_note_content(details)` - Generate markdown
- `get_filename(details)` - Generate "Title (Year).md" filename
- `get_poster_url(details)` - Get full poster URL from details (returns None if no poster available)

**Shared Disambiguation Logic (`lib/obsidian_utils.py`):**
- `extract_title_and_year(input)` - Extracts year from "Title (Year)" format
- `filter_results_by_year(results, year, media_type)` - Filters API results by year
- `find_exact_title_match(results, title, media_type)` - Auto-selects exact matches

This shared logic ensures consistent behavior across both 'add' and 'posters' commands.

**Shared Poster Utilities (`lib/poster_utils.py`):**
- `download_and_resize_poster(poster_url, output_path, width)` - Downloads from any URL (TMDB, IGDB, etc.), resizes, converts to JPEG
- `extract_yaml_frontmatter(content)` - Parses YAML frontmatter from markdown
- `update_frontmatter_with_poster(file_path, poster_filename)` - Updates frontmatter with poster wikilink

Used by both the integrated 'add' command poster download and the standalone 'posters' command to avoid code duplication. URL-agnostic design works with any image source.

## Commands

### Setup
```bash
pip install -r requirements.txt

# Set environment variables
export TMDB_API_KEY='your_key'              # For movies/TV
export IGDB_CLIENT_ID='your_client_id'      # For games
export IGDB_CLIENT_SECRET='your_secret'     # For games
```

### Main CLI Commands

**Add new media notes:**
```bash
# Movies (reads from stdin, newline-separated)
# Automatically downloads posters for movies/TV during creation
echo -e "Inception\nThe Matrix" | python obsidian_media_add.py add ~/vault backup.zip --media-type movie

# TV shows with custom poster width
python obsidian_media_add.py add ~/vault backup.zip --media-type tv --poster-width 300
# Then paste titles and press Ctrl+D

# Games with poster download
echo "Elden Ring" | python obsidian_media_add.py add ~/vault backup.zip --media-type game --poster-width 200
```

**Download posters for existing notes (retroactive):**
```bash
# Default: process all media types (movies, TV, games)
python obsidian_media_add.py posters ~/vault backup.zip

# Filter by media type
python obsidian_media_add.py posters ~/vault backup.zip --media-type game
python obsidian_media_add.py posters ~/vault backup.zip --media-type movie

# Custom width for all types
python obsidian_media_add.py posters ~/vault backup.zip --width 300
```

**Standardize game note titles:**
```bash
# Dry run to preview changes
python standardize_game_titles.py ~/vault --dry-run

# Apply changes with backup
python standardize_game_titles.py ~/vault backup.zip
```

This script:
- Renames game notes from various formats to "Name (Year).md"
- Handles existing formats:
  - "Name" (no parentheses) → "Name (Year).md"
  - "Name (Year).md" (already correct) → no change
  - "Name (Platform).md" (e.g., iPad, PC) → "Name (Year).md"
- Fetches release years from IGDB
- Updates wikilinks in all notes that reference renamed files
- Renames associated poster files and updates frontmatter
- Uses disambiguation for ambiguous titles
- Supports `--dry-run` mode to preview changes safely

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
- Both return 'poster_path' for poster downloads (used automatically in 'add' command)

**IGDB (games):**
- Uses 'name' and 'first_release_date' (Unix timestamp)
- Returns 'involved_companies' with developer/publisher flags
- Returns 'url' instead of external_ids
- Returns 'cover.image_id' for poster downloads (used automatically in 'add' command)
- Cover art downloaded using `cover_big` size (227x320) from IGDB image CDN

### Tag Detection

Scripts search for 'movie' or 'series' tags in:
1. YAML frontmatter: `tags: [movie]`
2. Hashtag format: `#movie`

Note: Avoids 'entertainment' tag (deprecated).

### Poster Download Workflow

**Integrated in 'add' command (all media types):**
1. After creating note, call `client.get_poster_url(details)` to get poster URL
2. Download poster from URL (TMDB for movies/TV, IGDB for games)
3. Resize maintaining aspect ratio to specified width (default: 200px)
4. Convert to JPEG (quality=85)
5. Save as "Title (Year).jpg" in same directory as note
6. Update YAML frontmatter: `poster: [[filename.jpg]]`

**Standalone 'posters' command (retroactive):**
1. Scan vault for files tagged 'movie', 'series', or 'game' without 'poster' property
2. Apply optional `--media-type` filter (movie, tv, game, or all)
3. Extract title and year from filename
4. Search appropriate API (TMDB for movie/tv, IGDB for games)
5. Follow same download/resize/save workflow as above

The 'posters' command supports `--media-type` filter to selectively process files. Default is 'all', which processes all media types but skips files that already have posters.

Both workflows use shared utilities from `lib/poster_utils.py`.

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
- `IGDB_CLIENT_SECRET` - Twitch application client secret
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

### Working with Poster Utilities

Common poster functionality lives in `lib/poster_utils.py` to avoid duplication:

```python
from lib.poster_utils import download_and_resize_poster, update_frontmatter_with_poster

# Download and save poster
if download_and_resize_poster(poster_path, output_file, tmdb_api_key, width):
    # Update note's frontmatter with wikilink
    update_frontmatter_with_poster(note_file, poster_filename)
```

Both the integrated 'add' command and standalone 'posters' command use these utilities. Any changes to poster download logic should be made in `poster_utils.py` to benefit both workflows.
