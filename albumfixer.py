import os
import requests
import shutil
import argparse
import sys
from datetime import datetime  # NEW: For timestamped logs
from PIL import Image, UnidentifiedImageError
from mutagen import File
import tkinter as tk
from tkinter import filedialog

'''
run with: python albumfixer.py -f "/path/to/music"
or just: python albumfixer.py
add -l/--log to save terminal output to a file
e.g.: python albumfixer.py -f "/path/to/music" -l

'''
# ------
# CONFIG
# ------
MAX_COVER_SIZE = (500, 500)
COVER_FILENAMES = ["folder.jpg", "cover.jpg"]
LRCLIB_URL = "https://lrclib.net/api/get"
MUSICBRAINZ_SEARCH = "https://musicbrainz.org/ws/2/release-group/"
COVERART_URL = "https://coverartarchive.org/release-group/"
ITUNES_SEARCH = "https://itunes.apple.com/search"
HEADERS = {"User-Agent": "AlbumFixer/1.0 (https://github.com/jevonlipsey)"}

# ------
# LOGGER
# ------

class Logger:
    """logger that writes to both terminal and a log file."""
    def __init__(self, log_path):
        self.terminal = sys.stdout
        self.log = open(log_path, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        # this is needed for compatibility with some systems
        self.terminal.flush()
        self.log.flush()

# -------
# HELPERS
# -------

def fix_cover_for_rockbox(image_path):
    """Converts any JPEG/PNG/WebP into Rockbox-safe baseline JPEG."""
    try:
        with Image.open(image_path) as img:
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            img.thumbnail(MAX_COVER_SIZE)
            fixed_path = os.path.join(os.path.dirname(image_path), "folder.jpg")
            
            if os.path.basename(image_path).lower() != "folder.jpg" and os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception:
                    pass 
                
            img.save(
                fixed_path,
                format="JPEG",
                quality=95,
                subsampling=0,
                progressive=False,
                optimize=True,
            )
            print(f"[FIX] | converted. baseline jpg saved: {fixed_path}")
            return fixed_path
    except UnidentifiedImageError:
        print(f"[ERR] | unreadable image: {image_path}")
    except Exception as e:
        print(f"[ERR] | error fixing {image_path}: {e}")
    return None


def get_album_info_from_tag(audio_path):
    """extract artist and album from metadata."""
    try:
        audio = File(audio_path)
        if not audio:
            return None, None
        artist = (
            audio.get("artist")[0]
            if isinstance(audio.get("artist"), list)
            else audio.get("artist")
        )
        album = (
            audio.get("album")[0]
            if isinstance(audio.get("album"), list)
            else audio.get("album")
        )
        return artist, album
    except Exception:
        return None, None


def _download_art_from_itunes(artist, album, dest_folder):
    """search itunes api. used by helper."""
    print(f"  [INFO] | trying apple music as a fallback...")
    try:
        params = {
            "term": album,
            "artistTerm": artist,
            "entity": "album",
            "attribute": "albumTerm",
            "limit": 1
        }
        res = requests.get(ITUNES_SEARCH, params=params, headers=HEADERS, timeout=10)
        res.raise_for_status()
        data = res.json()

        if data["resultCount"] == 0:
            print("  [WARN] | no apple music match found.")
            return None
            
        art_url = data["results"][0]["artworkUrl100"].replace("100x100bb", "1200x1200bb")

        img_data = requests.get(art_url, headers=HEADERS, timeout=10)
        if img_data.status_code == 200:
            dest_path = os.path.join(dest_folder, "folder.jpg")
            with open(dest_path, "wb") as f:
                f.write(img_data.content)
            print(f"  [ART] | downloaded art from apple music.")
            return dest_path
            
    except Exception as e:
        print(f"  [ERR] | error downloading from apple music: {e}")
        return None


def download_album_art(artist, album, dest_folder):
    """search musicbrainz release groups for album cover."""
    print(f"[INFO] | Searching MusicBrainz: Artist='{artist}', Album='{album}'")
    try:
        params = {
            "query": f'artist:"{artist}" AND releasegroup:"{album}"',
            "fmt": "json"
        }
        res = requests.get(MUSICBRAINZ_SEARCH, params=params, headers=HEADERS, timeout=10)
        res.raise_for_status()
        data = res.json()
        
        if not data.get("release-groups"):
            print(f"[WARN] | no musicbrainz release group found.")
            return None

        release_group_id = data["release-groups"][0]["id"]
        cover_url = f"{COVERART_URL}{release_group_id}/front-500"
        img_data = requests.get(cover_url, headers=HEADERS, timeout=10)
        
        if img_data.status_code == 200:
            dest_path = os.path.join(dest_folder, "folder.jpg")
            with open(dest_path, "wb") as f:
                f.write(img_data.content)
            print(f"[ART] | downloaded art from musicbrainz.")
            return dest_path
        else:
            print(f"[WARN] | no cover art found on musicbrainz.")
            return None
            
    except Exception as e:
        print(f"[ERR] | error downloading from musicbrainz: {e}")
        return None


def download_lyrics(artist, title, dest_folder):
    """download lyrics from lrclib.net and save .lrc or .txt."""
    try:
        params = {"artist_name": artist, "track_name": title}
        res = requests.get(LRCLIB_URL, params=params, timeout=10)
        if res.status_code != 200:
            return None

        data = res.json()
        lyric_type = ""
        
        if data.get("syncedLyrics"):
            lyrics = data["syncedLyrics"]
            ext = "lrc"
            lyric_type = "synced (.lrc)"
        elif data.get("plainLyrics"):
            lyrics = data["plainLyrics"]
            ext = "txt"
            lyric_type = "plain (.txt)"
        else:
            return None

        safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
        file_path = os.path.join(dest_folder, f"{safe_title}.{ext}")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(lyrics)
            
        print(f"  [LRC] | saved {lyric_type} lyrics for: {safe_title}")
        return file_path
    except Exception as e:
        print(f"  [ERR] | error fetching lyrics for {artist} - {title}: {e}")
        return None

def sanitize_filename(name):
    """removes invalid characters for filenames."""
    safe_name = "".join(c for c in name if c.isalnum() or c in " -_()").strip()
    safe_name = safe_name.replace("..", "").strip().rstrip(".")
    return safe_name

def parse_base_album_name(album_name):
    """tries to find the 'base' album name by stripping deluxe tags."""
    delimiters = [' (', ' [', ' - ']
    base_name = album_name
    
    first_index = len(album_name)
    for delim in delimiters:
        index = base_name.find(delim)
        if index != -1 and index < first_index:
            first_index = index
            
    if first_index != len(album_name):
        base_name = base_name[:first_index].strip()
        
    return base_name

def interactive_art_fix(artist, album, album_folder):
    """a cli helper to manually fix a failed art search."""
    print(f"\n[WARN] | automatic search failed for: \"{artist} - {album}\"")
        
    while True:
        print("\nwhat would you like to do?")
        print("(1) try a new search")
        print("(2) skip art for this album")
        choice = input("enter choice (1-2): ").strip()

        if choice == "2":
            print("[INFO] | skipping cover art for this album.")
            return None
        elif choice == "1":
            try:
                print(f"\ncurrent artist: \"{artist}\"")
                new_artist = input(f"enter new artist (or press enter to keep): ").strip()
                if not new_artist:
                    new_artist = artist
                
                print(f"\ncurrent album: \"{album}\"")
                new_album = input(f"enter new album: ").strip()
                if not new_album:
                    print("[WARN] | album name cannot be empty. please try again.")
                    continue

                base_new_album = parse_base_album_name(new_album)
                print(f"\n[INFO] | re-running search (will try '{base_new_album}' first)...")

                new_cover_path = download_album_art(new_artist, base_new_album, album_folder)

                if not new_cover_path and base_new_album != new_album:
                    print(f"[INFO] | base name failed. trying full literal name: '{new_album}'")
                    new_cover_path = download_album_art(new_artist, new_album, album_folder)
                
                if not new_cover_path:
                    print(f"[INFO] | musicbrainz failed. helper is trying apple music...")
                    new_cover_path = _download_art_from_itunes(new_artist, base_new_album, album_folder)
                
                if not new_cover_path and base_new_album != new_album:
                    new_cover_path = _download_art_from_itunes(new_artist, new_album, album_folder)

                if new_cover_path:
                    print("[INFO] | manual search successful.")
                    return new_cover_path
                else:
                    print("[WARN] | manual search failed with all sources. please try again.")
                    
            except Exception as e:
                print(f"[ERR] | an error occurred during manual search: {e}")
        else:
            print("[WARN] | invalid choice. enter '1' or '2'.")


def process_album_folder(album_folder, root_music_dir):
    """ensure cover art + lyrics exist for a given album folder."""
    
    audio_files = [
        f for f in os.listdir(album_folder) if f.lower().endswith((".flac", ".mp3"))
    ]
    if not audio_files:
        return False

    print(f"\n--- processing: {album_folder} ---")
    
    current_folder_name = os.path.basename(album_folder)
    name_parts = current_folder_name.split(" - ", 1)
    
    first_audio_path = os.path.join(album_folder, audio_files[0])
    tag_artist, tag_album = get_album_info_from_tag(first_audio_path)

    if len(name_parts) == 2:
        artist = name_parts[0].strip()
        album = name_parts[1].strip()
        print(f"[INFO] | using folder name for search: artist='{artist}', album='{album}'")
        if not tag_artist:
            tag_artist = artist
    elif tag_artist and tag_album:
        artist = tag_artist
        album = tag_album
        print(f"[INFO] | using file tags for search: artist='{artist}', album='{album}'")
    else:
        print("[WARN] | could not find artist/album from folder or tags. skipping.")
        return False

    # get cover art
    cover_found = False
    for cover_name in COVER_FILENAMES:
        cover_path = os.path.join(album_folder, cover_name)
        if os.path.exists(cover_path):
            fix_cover_for_rockbox(cover_path)
            cover_found = True
            break

    if not cover_found:
        base_album = parse_base_album_name(album)
        
        if base_album != album:
            print(f"[INFO] | found delimiters. trying base name: '{base_album}'")
        
        new_cover = download_album_art(artist, base_album, album_folder)

        if not new_cover and base_album != album:
            print(f"[INFO] | base name failed. trying full literal name: '{album}'")
            new_cover = download_album_art(artist, album, album_folder)
        
        if not new_cover:
            new_cover = interactive_art_fix(artist, album, album_folder)

        if new_cover:
            fix_cover_for_rockbox(new_cover)

    # get lyrics
    print("  checking for lyrics...")
    for audio_file in audio_files:
        track_path = os.path.join(album_folder, audio_file)
        try:
            audio = File(track_path)
            title = (
                audio.get("title")[0]
                if isinstance(audio.get("title"), list)
                else audio.get("title")
            )
            if not title:
                continue

            base_name = sanitize_filename(title)
            lrc_path = os.path.join(album_folder, f"{base_name}.lrc")
            txt_path = os.path.join(album_folder, f"{base_name}.txt")

            if not os.path.exists(lrc_path) and not os.path.exists(txt_path):
                if not tag_artist:
                    tag_artist = artist
                download_lyrics(tag_artist, title, album_folder)
        except Exception as e:
            print(f"  [ERR] | error processing track {audio_file}: {e}")

    #  cleanup audio file names
    print("  renaming audio files...")
    for audio_file in audio_files:
        track_path = os.path.join(album_folder, audio_file)
        try:
            audio = File(track_path)
            title = (
                audio.get("title")[0]
                if isinstance(audio.get("title"), list)
                else audio.get("title")
            )
            track_num_raw = audio.get("tracknumber")
            
            if not title:
                print(f"    [WARN] | skipping rename for {audio_file}, no title tag.")
                continue

            track_num_str = "00"
            if track_num_raw:
                track_num_str = str(track_num_raw[0]).split('/')[0].zfill(2)

            safe_title = sanitize_filename(title)
            ext = os.path.splitext(audio_file)[1]
            
            new_name = f"{track_num_str} - {safe_title}{ext}"
            new_path = os.path.join(album_folder, new_name)
            
            if track_path != new_path:
                os.rename(track_path, new_path)
                print(f"    renamed: {audio_file} -> {new_name}")

        except Exception as e:
            print(f"    [ERR] | rrror renaming {audio_file}: {e}")
            
    # organize folder structure
    print("  organizing folder...")
    try:
        current_folder_name = os.path.basename(album_folder)
        name_parts = current_folder_name.split(" - ", 1)
        
        if len(name_parts) == 2:
            artist_name = sanitize_filename(name_parts[0].strip())
            new_album_name = sanitize_filename(name_parts[1].strip())
            
            if not artist_name or not new_album_name:
                print(f"    [WARN] | could not extract valid artist/album name from '{current_folder_name}'. skipping organization.")
                return True
            
            artist_folder_path = os.path.join(root_music_dir, artist_name)
            os.makedirs(artist_folder_path, exist_ok=True)
            
            final_album_path = os.path.join(artist_folder_path, new_album_name)
            
            if os.path.abspath(album_folder) == os.path.abspath(final_album_path):
                print("    folder is already correctly organized.")
                return True

            if os.path.exists(final_album_path):
                print(f"    [WARN] | cannot move folder, destination already exists: {final_album_path}")
                return False
            else:
                shutil.move(album_folder, final_album_path)
                print(f"  [MV] | moved and renamed folder to: {final_album_path}")
                return True
        else:
            print(f"    [WARN] | folder name '{current_folder_name}' does not match 'Artist - Album' format. skipping organization.")
            return True

    except Exception as e:
        print(f"    [ERR] | error organizing folder: {e}")
        return False


def process_music_library(root_dir):
    """walk through all subfolders and process each album folder."""
    
    album_folders = []
    # walk folders "bottom-up" to safely rename/move parents
    for root, dirs, files in os.walk(root_dir, topdown=False):
        if ".rockbox" in dirs:
            dirs.remove(".rockbox")

        if any(f.lower().endswith((".mp3", "flac")) for f in files):
            is_sub_album = False
            for parent_folder in album_folders:
                 if root.startswith(parent_folder + os.sep):
                    is_sub_album = True
                    break
            if not is_sub_album:
                album_folders.append(root)
            
    if not album_folders:
        print("[WARN] | no album folders with audio files found.")
        return

    print(f"found {len(album_folders)} album folders to process...")
    album_folders.sort() 
    
    for folder_path in album_folders:
        process_album_folder(folder_path, root_dir)

# ----
# MAIN
# ----

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="clean and organize music albums for rockbox.")
    parser.add_argument(
        "-f", "--folder", 
        help="path to the music root directory. if not provided, a gui will open for selection."
    )
    parser.add_argument(
        "-l", "--log",
        action="store_true",
        help="save terminal output to a timestamped log file in the root directory."
    )
    args = parser.parse_args()
    
    root_directory = args.folder

    if not root_directory:
        try:
            root = tk.Tk()
            root.withdraw()
            root_directory = filedialog.askdirectory(title="select music root directory")
        except Exception as e:
            print(f"[ERR] | gui dialog failed: {e}")
            print("please run the script with the -f flag, e.g.: python albumfixer.py -f '/path/to/music'")
            sys.exit(1)

    if not root_directory:
        print("\nno directory selected, exiting.")
    else:
        if args.log:
            try:
                log_name = f"albumfixer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                log_path = os.path.join(root_directory, log_name)
                # redirect stdout and stderr to the logger
                sys.stdout = Logger(log_path)
                sys.stderr = sys.stdout
                print(f"logging output to: {log_path}\n")
            except Exception as e:
                print(f"[ERR] | failed to create log file: {e}")
                # continue without logging
        
        print(f"\nstarting album fix for: {root_directory}")
        process_music_library(root_directory)
        print("\nAll albums processed. Done.")