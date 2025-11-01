# albumfixer.py

A simple command-line tool for organizing music libraries and preparing them for music players.
I wrote this for intended use with rockbox + online album downloaders!

[![Demo GIF](https://i.imgur.com/ynkAgdS.gif)](https://youtu.be/LqGWlHftctU)

Click the GIF to watch the full script demo. 

## What It Does

- **Renames Files**: Cleans up track names to `01 - Track Title.flac` format using the file's metadata
- **Organizes Library**: Moves albums into an `Artist/Album` structure
- **Fetches Lyrics**: Automatically downloads synced (`.lrc`) or plain (`.txt`) lyrics from lrclib.net
- **Cover Art**: Converts existing art to Rockbox-compatible size and `folder.jpg` format, or fetches album art from MusicBrainz and Apple Music

## Smart Art Search

The script handles special releases intelligently:

1. **Base Name Search**: Strips delimiters like `(Deluxe)` or ' - Deluxe' to find the original release
2. **Full Name Search**: If that fails, tries the complete album name
3. **Manual Correction**: Prompts you to enter the correct artist/album if both fail

## Installation

1. Clone the repo:

```
git clone https://github.com/jevonlipsey/album-fixer.git
cd album-fixer
```

2. Install dependencies:

```
pip install -r requirements.txt
```

## Usage

**Note**: Folders need to be named in `Artist - Album` format.

### Command-Line

```bash
python albumfixer.py -f "/path/to/music"
```

### With Logging

Save terminal output to a log file:

```bash
python albumfixer.py -f "/path/to/music" -l
```

### GUI Dialog

Run without arguments to select a folder via pop-up:

```bash
python albumfixer.py
```

## Acknowledgements

Inspired by [rockbox-cover-art-fixer](https://github.com/SupItsZaire/rockbox-cover-art-fixer?tab=readme-ov-file) by SupItsZaire.
