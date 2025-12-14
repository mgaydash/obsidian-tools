# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a collection of Python scripts for managing and enriching movie/TV series notes in Obsidian vaults. The scripts interact with TMDB (The Movie Database) API to fetch metadata, rename files with release years, fix broken wikilinks, and download movie posters.

## Environment Setup

### Required Environment Variable
- `TMDB_API_KEY`: Required for all scripts. Get from https://www.themoviedb.org/ (Settings > API)
- Set via: `export TMDB_API_KEY='your_key_here'`

### Dependencies
Install via: `pip install -r requirements.txt`
- requests>=2.31.0
- PyYAML>=6.0.1
- Pillow>=10.0.0

## Scripts and Usage

### 1. obsidian_media_updater.py
Main script for renaming media files and adding metadata.

```bash
python obsidian_media_updater.py <vault_path> <backup_filename>
```

**What it does:**
- Finds markdown files tagged with `movie` or `series` (YAML or hashtag format)
- Skips files already in "Title (Year)" format
- Searches TMDB and prompts for disambiguation when multiple matches exist
- Renames files to "Title (Year).md" format
- Appends metadata: IMDB link, description with director/creator and top 3 actors as wikilinks

### 2. fix_wikilinks.py
Fixes broken wikilinks after files are renamed.

```bash
python fix_wikilinks.py <vault_path> <backup_filename> [--non-interactive]
```

**What it does:**
- Scans vault for files in "Title (Year)" format
- Finds wikilinks pointing to old names (e.g., `[[The Matrix]]`)
- Updates to new format (e.g., `[[The Matrix (1999)]]`)
- Preserves aliases (e.g., `[[Title|alias]]`)
- Prompts for disambiguation when multiple years exist (unless `--non-interactive`)

### 3. download_movie_posters.py
Downloads and embeds movie posters from TMDB.

```bash
python download_movie_posters.py <vault_path> <backup_filename> [--width WIDTH]
```

**What it does:**
- Finds markdown files tagged with `movie` without existing `poster` property
- Downloads posters from TMDB
- Resizes to specified width (default 200px, range 50-2000)
- Converts to JPEG format
- Saves with same base filename as markdown
- Updates YAML frontmatter with wikilink: `poster: ![[filename.jpg]]`

## Recommended Workflow Order

1. First: `obsidian_media_updater.py` to rename and add metadata
2. Second: `fix_wikilinks.py` to update all references
3. Third: `download_movie_posters.py` to add posters

## Architecture Notes

### Common Patterns

**YAML Frontmatter Handling:**
All scripts use `extract_yaml_frontmatter()` method that splits on `---` delimiters and uses `yaml.safe_load()`. Returns tuple of (frontmatter_dict, remaining_content).

**Tag Detection:**
Scripts check both YAML frontmatter (`tags: [movie]`) and hashtag format (`#movie`) by reading file content and checking both locations.

**TMDB API Structure:**
- Base URL: `https://api.themoviedb.org/3`
- Image base URL: `https://image.tmdb.org/t/p/original`
- obsidian_media_updater.py uses `/search/multi` endpoint (searches both movies and TV)
- download_movie_posters.py uses `/search/movie` endpoint (movies only)
- Both append `credits,external_ids` to get cast/crew and IMDB links

**Filename Sanitization:**
When renaming files, colons and slashes are replaced: `.replace(':', ' -').replace('/', '-').replace('\\', '-')` (obsidian_media_updater.py:259)

**Year Format Detection:**
Pattern: `r'.+\s\(\d{4}\)\.md$'` - matches "anything followed by space, parentheses with 4 digits"

### Interactive Disambiguation

All scripts prompt users when multiple matches exist:
- Display numbered list with metadata (title, year, description)
- Option 0 to skip
- obsidian_media_updater.py: shows overview + media type
- download_movie_posters.py: shows overview only
- fix_wikilinks.py: caches user choices within a file to avoid repeated prompts

### Backup Strategy

All scripts create full vault backups via `create_backup()` before making changes:
```python
zipfile.ZipFile(backup_filename, 'w', zipfile.ZIP_DEFLATED)
```

### Wikilink Format

- Cast/crew: `[[Name]]`
- Character with actor: `Character ([[Actor Name]])`
- Poster property: `poster: ![[filename.jpg]]` (not embedded in content, only frontmatter)

## File Structure Assumptions

- All markdown files are in vault subdirectories (uses `.rglob('*.md')`)
- Posters saved in same directory as markdown file
- No specific directory structure required
