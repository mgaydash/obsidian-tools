# Obsidian Tools

Collection of CLI tools for managing and organizing media notes (movies, TV shows, games) in Obsidian vaults. Fetches metadata from TMDB and IGDB, creates formatted notes, downloads posters, and provides utilities for standardizing and enhancing your media library.

## Installation

Editable install (recommended — keeps the tool runnable from the source tree
so `genre_mappings.yaml` resolves correctly):

```bash
pip install -e ".[dev]"     # runtime + test/dev dependencies
# or, for runtime only:
pip install -e .
```

This registers an `obsidian-tools` console command. Dependencies and tooling
config live in `pyproject.toml`.

## Setup

Set environment variables for the APIs you'll use:

```bash
# For movies and TV shows (required)
export TMDB_API_KEY='your_key_here'

# For games (optional)
export IGDB_CLIENT_ID='your_client_id'
export IGDB_CLIENT_SECRET='your_client_secret'
```

Get TMDB API key: https://www.themoviedb.org/ (Settings > API)
Get IGDB credentials: https://api-docs.igdb.com/#getting-started

## Usage

### Add Media Notes

Create new notes from titles (reads from stdin):

```bash
# Movies
echo -e "Inception (2010)\nThe Matrix (1999)" | \
  obsidian-tools add ~/vault --media-type movie

# TV shows
echo "Breaking Bad (2008)" | \
  obsidian-tools add ~/vault --media-type tv

# Games
echo "Elden Ring (2022)" | \
  obsidian-tools add ~/vault --media-type game

# Interactive mode (paste titles, then Ctrl+D)
obsidian-tools add ~/vault --media-type movie

# Back up the vault first (optional, off by default)
echo "Inception (2010)" | \
  obsidian-tools add ~/vault --media-type movie -b backup.zip
```

### Download Posters

Download and embed posters for existing movie/TV notes:

```bash
# Default 200px width
obsidian-tools posters ~/vault

# Custom width
obsidian-tools posters ~/vault --width 300

# Back up the vault first (optional, off by default)
obsidian-tools posters ~/vault -b backup.zip
```

## Features

- **Smart disambiguation**: Include year in parentheses (e.g., "Loot (2022)") for automatic matching
- **Optional backups**: Pass `-b/--backup <file.zip>` to zip the vault before making changes (off by default)
- **Rich metadata**: IMDB links, descriptions, cast/crew as wikilinks
- **Tag-based**: Works with files tagged `movie` or `series`

## What It Creates

For "Inception (2010)":

```markdown
---
tags:
  - movie
---

## Links
https://www.imdb.com/title/tt1375666

## Description
A thief who steals corporate secrets... Directed by [[Christopher Nolan]].
Starring Cobb ([[Leonardo DiCaprio]]), Arthur ([[Joseph Gordon-Levitt]]), ...
```

With posters command, adds:
```yaml
poster: [[Inception (2010).jpg]]
```
