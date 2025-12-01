# Obsidian Media File Updater

I use Obsidian to track movies, series, and other enterainment, but my vault was unfortunately poorly organized, and it was sometimes unclear what movie or show a file was identifying. To discretely identify the movie and series, this tool renames them with release years, and appends rich metadata from TMDB (The Movie Database).

## Features

- 🔍 Finds all notes tagged with `movie` or `series`
- 🎬 Fetches accurate data from TMDB
- 📝 Renames files to "Title (Year)" format
- 📋 Appends formatted metadata including:
  - IMDB link
  - Synopsis with director/creator and top 3 actors
  - Obsidian wikilinks for cast/crew
- 🖼️ Downloads and embeds movie posters from TMDB
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
- Are tagged with `movie` or `series` (either in YAML frontmatter or hashtag format)
- Are NOT already in "Title (Year)" format

**Examples of tags it recognizes:**

YAML format:
```yaml
---
tags:
  - movie
---
```

Hashtag format:
```markdown
#movie
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
## Links
https://www.imdb.com/title/tt0111161

## Description
Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency. Directed by [[Frank Darabont]]. Starring Ellis Boyd 'Red' Redding ([[Morgan Freeman]]), Andy Dufresne ([[Tim Robbins]]), Warden Norton ([[Bob Gunton]]).
```

## What Gets Added

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

## Downloading Movie Posters

After organizing your movie files, you can download and embed posters from TMDB using `download_movie_posters.py`.

### What It Does

The poster downloader:
- Finds all markdown files tagged with `movie`
- Skips files that already have a `poster` property in their YAML frontmatter
- Downloads the movie poster from TMDB
- Resizes the poster to a specified width (default: 200px, maintaining aspect ratio)
- Converts the poster to JPEG format if needed
- Saves the poster with the same base filename as the markdown file
- Updates the markdown file's YAML frontmatter with a wikilink to the poster image

### Usage

```bash
python download_movie_posters.py <vault_path> <backup_filename> [--width WIDTH]
```

### Examples

```bash
# Download posters at default 200px width
python download_movie_posters.py ~/Documents/ObsidianVault poster_backup.zip

# Download posters at custom 300px width
python download_movie_posters.py ~/Documents/ObsidianVault poster_backup.zip --width 300
```

### How It Works

1. **Finding Files**: Searches for markdown files tagged with `movie` that don't already have a poster
2. **Searching TMDB**: If the filename includes a year (e.g., "Inception (2010).md"), it uses that to filter results
3. **Disambiguation**: If multiple matches are found, prompts you to select the correct movie
4. **Processing**: Downloads the poster, resizes it, converts to JPEG, and saves it next to the markdown file
5. **Updating Frontmatter**: Adds a `poster: ![[filename.jpg]]` property to the YAML frontmatter

### Example Transformation

**Before:**
```yaml
---
tags:
  - movie
---
```

**After:**
```yaml
---
tags:
  - movie
poster: ![[Inception (2010).jpg]]
---
```

The poster image `Inception (2010).jpg` will be saved in the same directory as the markdown file.

### Options

- `--width WIDTH`: Set the poster width in pixels (default: 200, range: 50-2000)

### Notes

- Only processes files tagged with `movie` (not `series`)
- Skips files that already have a `poster` property in frontmatter
- Posters are always converted to JPEG format for consistency
- Maintains aspect ratio when resizing
- Requires the same TMDB API key as the media updater

## Requirements

- Python 3.7+
- requests
- PyYAML
- Pillow

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

## Fixing Broken Wikilinks

After renaming your files with `obsidian_media_updater.py`, any wikilinks in other notes that referenced the old file names (without years) will be broken. Use `fix_wikilinks.py` to automatically update these links.

### What It Does

The wikilink fixer:
- Scans your vault for files in "Title (Year)" format
- Finds wikilinks that point to old names (e.g., `[[The Matrix]]`)
- Updates them to the new format (e.g., `[[The Matrix (1999)]]`)
- Preserves aliases (e.g., `[[The Matrix|great movie]]` becomes `[[The Matrix (1999)|great movie]]`)
- Handles disambiguation when multiple years exist for the same title

### Usage

```bash
python fix_wikilinks.py <vault_path> <backup_filename> [--non-interactive]
```

### Example

```bash
python fix_wikilinks.py ~/Documents/ObsidianVault wikilink_backup.zip
```

### Interactive Mode (Default)

When the script finds a link that could point to multiple files (e.g., both "The Office (2001)" and "The Office (2005)" exist), it will prompt you to choose:

```
🔗 Multiple files match the link target 'The Office':
--------------------------------------------------------------------------------
1. The Office (2005)
2. The Office (2001)
3. Keep original (don't update this link)
--------------------------------------------------------------------------------
Select the correct file (or keep original):
```

### Non-Interactive Mode

Use `--non-interactive` to skip ambiguous links instead of prompting:

```bash
python fix_wikilinks.py ~/Documents/ObsidianVault wikilink_backup.zip --non-interactive
```

### Example Session

```
🔗 Obsidian Wikilink Fixer
================================================================================
Vault: /Users/me/Documents/Vault
Backup: wikilink_backup.zip
Mode: Interactive
================================================================================
Creating backup: wikilink_backup.zip
✓ Backup created successfully

🔍 Building file mapping...
✓ Found 5 base title(s) with year versions

🔍 Scanning 42 markdown files...
--------------------------------------------------------------------------------
✓ Movie Reviews.md: Updated 3 link(s)
✓ Favorites.md: Updated 1 link(s)
✓ 2024 Watchlist.md: Updated 2 link(s)

================================================================================
📊 SUMMARY
================================================================================
Files scanned: 42
Files with updates: 3
Links updated: 6

✅ Done!
```

## Recommended Workflow

1. **First**, run the media updater to rename files and add metadata:
   ```bash
   python obsidian_media_updater.py ~/Documents/Vault media_backup.zip
   ```

2. **Second**, run the wikilink fixer to update all references:
   ```bash
   python fix_wikilinks.py ~/Documents/Vault wikilink_backup.zip
   ```

3. **Third**, run the poster downloader to add movie posters:
   ```bash
   python download_movie_posters.py ~/Documents/Vault poster_backup.zip
   ```

This ensures all your files are properly renamed, all links throughout your vault are updated, and movie posters are embedded in your notes.

## License

Free to use and modify as needed.
