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

### Configure a default vault (optional)

Save your vault path once so you can omit it from every command:

```bash
obsidian-tools configure --vault-path ~/vault
obsidian-tools configure --show          # print saved settings
obsidian-tools configure                 # prompt interactively
```

Settings are stored at `~/.config/obsidian-tools/config.json` (respecting
`XDG_CONFIG_HOME`). After configuring, the vault path is optional on `add` and
`posters`; passing one explicitly always overrides the saved value.

## Usage

### Add Media Notes

Create new notes from titles. The media type is the positional argument;
titles can follow as arguments, or (if none are given) are read from stdin,
one per line. The vault path defaults to the configured value, and
`--vault-path` overrides it:

```bash
# Titles as arguments (uses the configured vault path)
obsidian-tools add movie "Inception (2010)" "The Matrix (1999)"

# Titles from stdin (used when no title arguments are given)
echo -e "Inception (2010)\nThe Matrix (1999)" | \
  obsidian-tools add movie

# TV shows, to an explicit vault
echo "Breaking Bad (2008)" | \
  obsidian-tools add tv --vault-path ~/vault

# Games
echo "Elden Ring (2022)" | \
  obsidian-tools add game

# Interactive mode (paste titles, then Ctrl+D)
obsidian-tools add movie

# Back up the vault first (optional, off by default)
echo "Inception (2010)" | \
  obsidian-tools add movie -b backup.zip
```

### Download Posters

Download and embed posters for existing movie/TV notes (uses the configured
vault path; `--vault-path` overrides it):

```bash
# Default 200px width
obsidian-tools posters

# Custom width
obsidian-tools posters --width 300

# Explicit vault + backup (both optional)
obsidian-tools posters --vault-path ~/vault -b backup.zip
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
