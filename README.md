# Obsidian Media Note Manager

CLI tool for managing media notes (movies, TV shows, games) in Obsidian vaults. Fetches metadata from TMDB and IGDB, creates formatted notes, and downloads posters.

## Installation

```bash
pip install -r requirements.txt
```

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
  python obsidian_media_add.py add ~/vault backup.zip --media-type movie

# TV shows
echo "Breaking Bad (2008)" | \
  python obsidian_media_add.py add ~/vault backup.zip --media-type tv

# Games
echo "Elden Ring (2022)" | \
  python obsidian_media_add.py add ~/vault backup.zip --media-type game

# Interactive mode (paste titles, then Ctrl+D)
python obsidian_media_add.py add ~/vault backup.zip --media-type movie
```

### Download Posters

Download and embed posters for existing movie/TV notes:

```bash
# Default 200px width
python obsidian_media_add.py posters ~/vault backup.zip

# Custom width
python obsidian_media_add.py posters ~/vault backup.zip --width 300
```

## Features

- **Smart disambiguation**: Include year in parentheses (e.g., "Loot (2022)") for automatic matching
- **Automatic backups**: Creates zip backup before making changes
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
