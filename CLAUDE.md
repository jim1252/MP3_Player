# MP3 Player - notes for Claude

James's MP3 player for the Raspberry Pi, written in Python with Tkinter (window) and pygame (sound).

## About James
- Can get by in Python and is better at reading it than writing it. Keep code plain and
  well commented, explain changes in everyday language, and avoid clever tricks.
- The code is indented with **tabs** - keep it that way.
- Happy for the window layout to grow or change as features are added.

## Files
- `MP3_Dev.py` - **the player. All new work goes here.** Run with `python MP3_Dev.py`.
- `visualiser.py` - the bouncing bars. Decodes each song in a background thread with
  pygame + numpy, then draws 30 times a second in step with the song.
- `tooltip.py` - hover tips for buttons. `Tooltip(widget, 'text')`, or pass a function for
  tips that change (e.g. Shuffle on/off).
- `make_icons.py` - draws all the `icons/btn_*.png` button pictures in one matching style
  (black with green). To change a button's look, edit this and re-run it - don't edit the PNGs.
- `MP3_Good.py` - an older working version kept for reference. Don't change it; it still uses
  the old icons (`icons/back.png`, `play.png` etc.), so don't delete those.
- `audio.py` - an early Tkinter learning file, not part of the player.
- `MP3_player_notes.txt` - setup steps (venv, pip installs). Update it when a new package is needed.
- `settings.json` - saved music/playlist folders. Created when the player runs; not in git.

## How MP3_Dev.py works
- `song_paths` holds the full path of every song, in the same order as the playlist listbox.
- `play_song(index)` is the one place songs get started - use it for anything that plays a song.
- pygame can't say where a song is after seeking, so `seek_offset` remembers where playback last
  started (0, or where the slider/skip buttons jumped to). `song_position()` adds pygame's
  `get_pos()` to it; the visualiser uses this.
- `play_time()` moves the slider along once a second.
- Repeat modes: `REPEAT_OFF`, `REPEAT_SONG`, `REPEAT_ALL`. Shuffle is the `shuf` IntVar.
- Playlists are saved as `.m3u` files.

## Dependencies
`pygame`, `mutagen`, `eyed3`, `pillow`, `numpy`, plus `python3-tk` from apt.

## Working on it
- Make changes on a new branch, push it, and open a pull request for James to try on the Pi
  before he merges it on GitHub. Don't push straight to `main`.
- Describe changes in the pull request in plain language.
- Ideas mentioned for later: a matching music-note picture for songs with no album art
  (the current one is the old teal style).
