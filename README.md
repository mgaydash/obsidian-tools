# Obsidian Media File Updater

Automatically finds movie and series notes in your Obsidian vault, renames them with release years, and appends rich metadata from TMDB (The Movie Database).

## Features

- 🔍 Finds all notes tagged with `entertainment`, `movie`, or `series`
- 🎬 Fetches accurate data from TMDB
- 📝 Renames files to "Title (Year)" format
- 📋 Appends formatted metadata including:
  - IMDB link
  - Synopsis with director/creator and top 3 actors
  - Obsidian wikilinks for cast/crew
- 💾 Creates a backup before making changes
- 🎯 Smart disambiguation when multiple matches are found

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get a TMDB API Key

1. Create a free account at [https://www.themoviedb.org/](https://www.themoviedb.org/)
2. Go to **Settings > API**
3. Request an API key (choose "Developer" option)
4. Copy your API key

### 3. Set Environment Variable

**Linux/Mac:**
```bash
export TMDB_API_KEY='your_api_key_here'
```

**Windows (Command Prompt):**
```cmd
set TMDB_API_KEY=your_api_key_here
```

**Windows (PowerShell):**
```powershell
$env:TMDB_API_KEY='your_api_key_here'
```

## Usage

```bash
python obsidian_media_updater.py <vault_path> <backup_filename>
```

### Example

```bash
python obsidian_media_updater.py ~/Documents/ObsidianVault backup_2024-10-24.zip
```

## How It Works

### 1. Finding Files

The script searches for markdown files that:
- Are tagged with `entertainment`, `movie`, or `series` (either in YAML frontmatter or hashtag format)
- Are NOT already in "Title (Year)" format

**Examples of tags it recognizes:**

YAML format:
```yaml
---
tags:
  - entertainment
  - movie
---
```

Hashtag format:
```markdown
#entertainment #movie
```

### 2. Disambiguation

When multiple matches are found, you'll see a numbered list:

```
📽️  Multiple results found for 'The Office':
--------------------------------------------------------------------------------
1. The Office (2005) [TV]
   A mockumentary on a group of typical office workers...

2. The Office (2001) [TV]
   The story of an office that faces closure when the company...

0. Skip this file
--------------------------------------------------------------------------------
Select the correct match (0 to skip): 
```

### 3. File Transformation

**Before:**
```
The Shawshank Redemption.md
```

**After:**
```
The Shawshank Redemption (1994).md
```

With appended content:
```markdown
---
tags:
  - entertainment
rating:
---

## Links
https://www.imdb.com/title/tt0111161

## Description
Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency. Directed by [[Frank Darabont]]. Starring Ellis Boyd 'Red' Redding ([[Morgan Freeman]]), Andy Dufresne ([[Tim Robbins]]), Warden Norton ([[Bob Gunton]]).
```

## What Gets Added

### YAML Frontmatter
```yaml
---
tags:
  - entertainment
rating:
---
```

### IMDB Link
Clean IMDB URL without query parameters

### Description
- 2-3 sentence synopsis from TMDB
- Director (movies) or Creator (TV shows) as wikilink
- Top 3 billed actors with character names and wikilinks
- Format: `Character ([[Actor Name]])`

## File Exclusions

Files already in "Title (Year)" format are automatically skipped:
- ✅ `Inception (2010).md` - Skipped
- ❌ `Inception.md` - Processed

## Safety Features

1. **Automatic Backup**: Creates a complete zip backup before any changes
2. **Overwrite Protection**: Prompts before overwriting existing files
3. **Skip Option**: You can skip any file during disambiguation
4. **Detailed Logging**: Shows exactly what's happening at each step

## Troubleshooting

### "TMDB_API_KEY environment variable not set"
Make sure you've exported the environment variable in your current terminal session.

### "No results found for 'Title'"
- The title might be too vague or misspelled
- Try renaming the file to be more specific before running the script
- You can manually skip it and process it later

### "Target file already exists"
Another file with the same "Title (Year)" format already exists. You'll be prompted whether to overwrite.

## Requirements

- Python 3.7+
- requests
- PyYAML

## Notes

- The script uses TMDB's official API (not web scraping)
- All data is fetched in real-time for accuracy
- Wikilinks are automatically formatted for Obsidian
- The script handles both movies and TV series

## Example Session

```
🎬 Obsidian Media File Updater
================================================================================
Vault: /Users/me/Documents/Vault
Backup: backup.zip
================================================================================
Creating backup: backup.zip
✓ Backup created successfully

🔍 Scanning for media files...
--------------------------------------------------------------------------------
✓ Found: Inception.md
✓ Found: Breaking Bad.md
⊘ Skipping (already formatted): The Matrix (1999).md

📋 Found 2 file(s) to process
================================================================================

================================================================================
Processing: Inception
================================================================================
✓ Successfully processed: Inception (2010).md

================================================================================
Processing: Breaking Bad
================================================================================
✓ Successfully processed: Breaking Bad (2008).md

================================================================================
📊 SUMMARY
================================================================================
✓ Processed: 2
⊘ Skipped: 0
📦 Backup: backup.zip

✅ Done!
```

## License

Free to use and modify as needed.
