from tkinter import *
from PIL import ImageTk,Image
import pygame
from tkinter import filedialog
from tkinter import messagebox
import time
from mutagen.mp3 import MP3
import tkinter.ttk as ttk
from random import randint
import eyed3
import os
from io import BytesIO
import json
import sys
import ctypes
from datetime import datetime, date
from visualiser import Visualiser
from tooltip import Tooltip

root = Tk()
root.title('My MP3')
root.geometry("960x840")
# Smallest the window can be dragged to before things get squashed
root.minsize(960, 700)
pygame.mixer.init()

# Folder this script lives in - used to find the icons wherever you run it from
script_dir = os.path.dirname(os.path.abspath(__file__))

# Where the file dialog opens if no music folder is set - starts at the current folder,
# then remembers the folder the last songs were added from
last_folder = os.getcwd()

# ---------------- Settings ----------------
# Settings are kept in settings.json next to this script so they're remembered between runs
settings_file = os.path.join(script_dir, 'settings.json')
settings = {
	'music_folder': '',     # where Add Songs opens ('' = not set)
	'playlist_folder': '',  # where Open/Save Playlist opens ('' = not set)
	# The rest are saved when the player closes, so it starts up the way you left it
	'volume': 1.0,          # volume slider, 0.0 to 1.0
	'muted': False,
	'shuffle': False,
	'repeat': 0,            # REPEAT_OFF, REPEAT_SONG or REPEAT_ALL
	'last_playlist': '',    # the playlist file that was open ('' = none)
	'last_song': -1,        # position in that playlist of the song that was loaded (-1 = none)
	'last_position': 0,     # how far into that song it had got, in seconds
}

def load_settings():
	try:
		with open(settings_file, 'r', encoding='utf-8') as f:
			saved = json.load(f)
		# Only take settings we know about, and only if they're the right kind of value
		# (text, number, True/False), so an old or hand-edited file can't break anything
		for key, default in settings.items():
			value = saved.get(key)
			if type(default) is float and type(value) in (int, float):
				# A whole number like 1 is fine for the volume too
				settings[key] = float(value)
			elif type(value) is type(default):
				settings[key] = value
	except FileNotFoundError:
		# First run - no settings saved yet
		pass
	except (OSError, ValueError) as e:
		print('Could not read settings:', e)

def save_settings():
	try:
		with open(settings_file, 'w', encoding='utf-8') as f:
			json.dump(settings, f, indent=4)
	except OSError as e:
		messagebox.showerror('Settings', f"Couldn't save settings:\n{e}")

# ---------------- Play history ----------------
# How many times each song has been played and when it was last played, kept in
# play_history.json next to settings.json (not in git). It's keyed by each song's full path,
# so a song has one count whichever playlist it's played from. Looks like:
#   {"/home/james/Music/Anchor.mp3": {"plays": 12, "last_played": "2026-11-26 10:59"}}
# Moving or renaming a song file means it starts again from 0.
history_file = os.path.join(script_dir, 'play_history.json')
play_history = {}

# Write a song's path the same way every time, e.g. '/home/james/Music//Anchor.mp3' and
# '/home/james/Music/./Anchor.mp3' both become '/home/james/Music/Anchor.mp3'.
# The play history looks songs up by path, so the same song must always have the same path -
# whether it came from the file picker or from a playlist file.
def tidy_path(path):
	return os.path.normpath(os.path.abspath(path))

# A song counts as played after this many seconds of listening (or halfway, if it's shorter)
COUNT_AFTER_SECONDS = 30

def load_history():
	try:
		with open(history_file, 'r', encoding='utf-8') as f:
			saved = json.load(f)
		if isinstance(saved, dict):
			for path, entry in saved.items():
				add_saved_history(path, entry)
	except FileNotFoundError:
		# Nothing has been played yet
		pass
	except (OSError, ValueError) as e:
		print('Could not read play history:', e)

# Put one entry from play_history.json into play_history, with its path tidied.
# Older versions of the player could save the same song under two slightly different paths,
# so if the tidied path is already there, the two are joined: plays added up, latest time kept.
def add_saved_history(path, entry):
	if not isinstance(entry, dict):
		return
	path = tidy_path(path)
	if path not in play_history:
		play_history[path] = entry
		return
	plays = play_count(path)
	if isinstance(entry.get('plays'), int):
		plays += entry['plays']
	latest = last_played(path)
	other = entry.get('last_played')
	# The text "2026-11-26 10:59" sorts in date order, so the bigger one is the later time
	if isinstance(other, str) and other > latest:
		latest = other
	play_history[path] = {'plays': plays, 'last_played': latest}

def save_history():
	try:
		with open(history_file, 'w', encoding='utf-8') as f:
			json.dump(play_history, f, indent=4)
	except OSError as e:
		# Not worth a pop-up in the middle of a song - just mention it
		print('Could not save play history:', e)

# How many times a song has been played (0 if never)
def play_count(path):
	entry = play_history.get(path)
	if isinstance(entry, dict) and isinstance(entry.get('plays'), int):
		return entry['plays']
	return 0

# When a song was last played, as text like "2026-11-26 10:59" ('' if never)
def last_played(path):
	entry = play_history.get(path)
	if isinstance(entry, dict) and isinstance(entry.get('last_played'), str):
		return entry['last_played']
	return ''

# Last played in a short form for the table: "Today 10:59", "Yesterday 21:30" or "24 Nov 2026"
def short_last_played(path):
	text = last_played(path)
	if not text:
		return ''
	try:
		when = datetime.strptime(text, '%Y-%m-%d %H:%M')
	except ValueError:
		return text
	days_ago = (date.today() - when.date()).days
	if days_ago == 0:
		return 'Today ' + when.strftime('%H:%M')
	if days_ago == 1:
		return 'Yesterday ' + when.strftime('%H:%M')
	return when.strftime('%d %b %Y')

# Add one play to a song, save the history, and update its row(s) and the details panel
def count_play(path):
	entry = play_history.get(path)
	if not isinstance(entry, dict):
		entry = {}
	entry['plays'] = play_count(path) + 1
	entry['last_played'] = datetime.now().strftime('%Y-%m-%d %H:%M')
	play_history[path] = entry
	save_history()
	# The same song can be in the playlist more than once, so update every row it's in
	for index, song in enumerate(song_paths):
		if song == path:
			song_display.set(str(index), 'plays', play_count(path))
			song_display.set(str(index), 'last', short_last_played(path))
	# If the details panel is showing this song, refresh it so the count goes up there too
	shown = selected_index()
	if shown is not None and song_paths[shown] == path:
		song_info(path)

# Called once a second while a song is playing (from play_time).
# Adds up how long it's actually been listened to - jumping ahead with the slider doesn't count -
# and counts the play once it gets far enough.
def listened_a_second():
	global listened_seconds, play_counted
	if play_counted or current_index is None:
		return
	listened_seconds += 1
	needed = min(COUNT_AFTER_SECONDS, song_length / 2)
	if listened_seconds >= needed:
		play_counted = True
		count_play(song_paths[current_index])

# A folder from settings, if it's set and still exists (a USB stick might be unplugged)
def setting_folder(key):
	folder = settings[key]
	if folder and os.path.isdir(folder):
		return folder
	return None

# Where Add Songs opens: the music folder if set, otherwise wherever songs were last added from
def music_start_folder():
	return setting_folder('music_folder') or last_folder

# Where Open/Save Playlist opens: the playlist folder if set,
# otherwise the folder of the open playlist, otherwise wherever songs were last added from
def playlist_start_folder():
	folder = setting_folder('playlist_folder')
	if folder:
		return folder
	if playlist_file:
		return os.path.dirname(playlist_file)
	return last_folder

load_settings()
load_history()

# Full path of every song in the playlist, in the same order as the listbox.
# The listbox only shows the song name; this list remembers where each file
# actually lives, so songs from different folders all play.
song_paths = []

# Position in the playlist of the song that's loaded (None = nothing loaded yet)
current_index = None
song_length = 0
stopped = True
paused = False
# ID of the scheduled play_time update, so only one timer ever runs
timer_id = None
# Where in the song (seconds) playback last started from - 0, or wherever the slider was dragged to.
# pygame only says how long it's been playing since then, so we add the two together.
seek_offset = 0
# The playlist file that's open (None = a new playlist that hasn't been saved yet)
playlist_file = None
# True when songs have been added, removed or moved since the last save
playlist_changed = False
# True when the Mute button is on - the volume slider stays where it was so unmuting puts it back
muted = False
# When the player starts up it gets ready to carry on where it left off.
# resume_index is the song and resume_at is how many seconds in; Play starts from there.
# Both go back to None as soon as any song is played or the playlist changes.
resume_index = None
resume_at = None
# Seconds the current song has actually been listened to, and whether it's been counted yet
listened_seconds = 0
play_counted = False

# Turn a full path into the name shown in the playlist
def display_name(path):
	return os.path.splitext(os.path.basename(path))[0]

# ---------------- The playlist table ----------------
# The playlist is a table (a ttk Treeview) with these columns.
# Each row's id is its position in song_paths as text ('0', '1', '2' ...), so row '3' is song_paths[3].
PLAYLIST_COLUMNS = ('num', 'title', 'artist', 'album', 'time', 'plays', 'last')
COLUMN_HEADINGS = {'num': '#', 'title': 'Title', 'artist': 'Artist', 'album': 'Album', 'time': 'Time', 'plays': 'Plays', 'last': 'Last played'}

# Length of a song as minutes:seconds for the Time column, e.g. 3:42
def short_time(seconds):
	minutes, secs = divmod(int(seconds), 60)
	return f'{minutes}:{secs:02d}'

# Put one song into the table as a row, at the bottom
def add_row(index):
	path = song_paths[index]
	tags = read_tags(path)
	song_display.insert('', END, iid=str(index), values=(index + 1, tags['title'], tags['artist'], tags['album'], short_time(get_length(path)),
		play_count(path), short_last_played(path)))

# Empty the table (song_paths isn't touched)
def clear_rows():
	song_display.delete(*song_display.get_children())

# Rebuild the whole table from song_paths - used after songs are removed, moved or sorted,
# because every row's number changes
def refresh_playlist():
	clear_rows()
	for index in range(len(song_paths)):
		add_row(index)

# Position in the playlist of the selected row (None if nothing is selected)
def selected_index():
	selected = song_display.selection()
	if not selected:
		return None
	return int(selected[0])

# Add one file to the playlist (used by both add functions)
def add_to_playlist(path):
	global last_folder
	path = tidy_path(path)
	song_paths.append(path)
	mark_changed()
	add_row(len(song_paths) - 1)
	last_folder = os.path.dirname(path)
	# If nothing is selected yet, select the first song
	if selected_index() is None:
		song_display.selection_set('0')
	update_summary()

# ---------------- Sorting ----------------
# Clicking a column heading sorts the playlist by it; clicking it again sorts the other way.
# sort_column is the column it was last sorted by (None = not sorted, or moved about since).
sort_column = None
sort_reverse = False

# Track number as a number for sorting (songs without one go first)
def track_number(tags):
	if isinstance(tags['track'], int):
		return tags['track']
	return 0

# What to sort each song by, for each column. Lower case so 'abba' and 'ABBA' sort together.
# Artist sorts by album then track within each artist, and Album sorts by track within each album,
# so albums stay in their proper order.
def sort_key(path, column):
	tags = read_tags(path)
	title = str(tags['title']).lower()
	artist = str(tags['artist']).lower()
	album = str(tags['album']).lower()
	if column == 'title':
		return (title, artist)
	if column == 'artist':
		return (artist, album, track_number(tags), title)
	if column == 'album':
		return (album, track_number(tags), title)
	if column == 'plays':
		return (play_count(path), title)
	if column == 'last':
		# The saved text "2026-11-26 10:59" sorts in date order as it is
		return (last_played(path), title)
	# 'time'
	return (get_length(path), title)

def sort_playlist(column):
	global sort_column, sort_reverse, current_index
	if not song_paths:
		return
	# Same column again = flip the order. A new column = A to Z (or shortest first),
	# except Plays and Last played, which start with the most played / most recent at the top.
	if column == sort_column:
		reverse = not sort_reverse
	elif column in ('plays', 'last'):
		reverse = True
	else:
		reverse = False
	# Remember which songs are playing and selected, so we can find them again after sorting
	playing = song_paths[current_index] if current_index is not None else None
	picked = selected_index()
	picked_path = song_paths[picked] if picked is not None else None
	song_paths.sort(key=lambda path: sort_key(path, column), reverse=reverse)
	if playing is not None:
		current_index = song_paths.index(playing)
	refresh_playlist()
	if current_index is not None:
		highlight(current_index)
	elif picked_path is not None:
		highlight(song_paths.index(picked_path))
	# The new order gets saved with the playlist
	mark_changed()
	# mark_changed() clears the arrow, so set it after
	sort_column = column
	sort_reverse = reverse
	show_sort_arrow()

# Put ▲ (A to Z) or ▼ (Z to A) on the heading the playlist is sorted by, and set up the
# headings so clicking them sorts. The # column just shows the position, so it doesn't sort.
def show_sort_arrow():
	for column in PLAYLIST_COLUMNS:
		text = COLUMN_HEADINGS[column]
		if column == sort_column:
			text += ' ▼' if sort_reverse else ' ▲'
		if column == 'num':
			song_display.heading(column, text=text, anchor=E)
		else:
			# 'column=column' makes each heading remember its own column name
			song_display.heading(column, text=text, anchor=W, command=lambda column=column: sort_playlist(column))

# Turn a number of seconds into something short like "1h 32m" or "23m 45s"
def format_total(seconds):
	hours, rest = divmod(int(seconds), 3600)
	minutes, secs = divmod(rest, 60)
	if hours:
		return f'{hours}h {minutes}m'
	return f'{minutes}m {secs}s'

# Show how many songs are in the playlist and how long it lasts, e.g. "24 songs · 1h 32m"
def update_summary():
	count = len(song_paths)
	if count == 0:
		playlist_summary.config(text='No songs')
		return
	total = 0
	for path in song_paths:
		total += get_length(path)
	word = 'song' if count == 1 else 'songs'
	playlist_summary.config(text=f'{count} {word} · {format_total(total)}')

# Add song Function
def add_song():
	song = filedialog.askopenfilename(initialdir=music_start_folder(), title="Choose A Song", filetypes=(("mp3 Files", "*.mp3"), ))
	# Pressing Cancel returns an empty string
	if song:
		add_to_playlist(song)

#Add multiple songs to playlist
def add_multiple():
	songs = filedialog.askopenfilenames(initialdir=music_start_folder(), title="Choose Songs", filetypes=(("mp3 Files", "*.mp3"), ))
	for song in songs:
		add_to_playlist(song)

# Clear the song name and info panels
def clear_song_labels():
	current_song.config(text="")
	song_info_label.config(text="No Song Selected")
	show_album_art(None)

# delete a song
def delete_song():
	global current_index
	index = selected_index()
	if index is None:
		return
	if index == current_index:
		# Deleting the song that's playing - stop it
		stop()
		current_index = None
		clear_song_labels()
	elif current_index is not None and index < current_index:
		# A song above the playing one has gone, so it moves up one place
		current_index -= 1
	del song_paths[index]
	# Every song below it moves up a number, so redo the table
	refresh_playlist()
	mark_changed()
	update_summary()
	if song_paths:
		highlight(current_index if current_index is not None else min(index, len(song_paths) - 1))

# Delete all songs from playlist
def delete_all_songs():
	global current_index
	stop()
	if song_paths:
		mark_changed()
	clear_rows()
	song_paths.clear()
	current_index = None
	clear_song_labels()
	update_summary()

# Stop the once-a-second timer if it's running
def cancel_timer():
	global timer_id
	if timer_id is not None:
		root.after_cancel(timer_id)
		timer_id = None

# Runs once a second while a song is loaded to move the slider along
def play_time():
	global timer_id
	timer_id = None
	if stopped:
		return
	converted_length = time.strftime('%H:%M:%S', time.gmtime(song_length))

	if not paused:
		listened_a_second()
		next_time = int(my_slider.get()) + 1
		if next_time >= int(song_length):
			# Song has finished
			status_bar.config(text=f'Time Elapsed: {converted_length} of {converted_length}  ')
			next_track(song_finished=True)
			return
		my_slider.config(value=next_time)
		converted_time = time.strftime('%H:%M:%S', time.gmtime(next_time))
		status_bar.config(text=f'Time Elapsed: {converted_time} of {converted_length}  ')

	# Check again in a second
	timer_id = root.after(1000, play_time)

# Move the red bar in the playlist to a song
def highlight(index):
	row = str(index)
	song_display.selection_set(row)
	song_display.focus(row)
	# Scroll the table so the row can be seen
	song_display.see(row)

# Tags of songs we've already read, so each file only gets read once
# (the table needs them for every row, and sorting needs them for every song)
song_tags = {}

# Read the tags from a song, falling back to sensible values if any are missing
def read_tags(path):
	if path not in song_tags:
		song_tags[path] = read_tags_from_file(path)
	return song_tags[path]

def read_tags_from_file(path):
	tags = {
		'title': display_name(path), 'artist': 'Unknown', 'album': 'Unknown',
		'track': 'Unknown', 'composer': 'Unknown', 'publisher': 'Unknown', 'genre': 'None',
	}
	try:
		audio = eyed3.load(path)
	except Exception as e:
		print('Could not read tags:', e)
		audio = None
	# eyed3 gives None for unreadable files and audio.tag is None if a file has no tags
	if audio is None or audio.tag is None:
		return tags
	tag = audio.tag
	tags['title'] = tag.title or tags['title']
	tags['artist'] = tag.artist or tags['artist']
	tags['album'] = tag.album or tags['album']
	if tag.track_num and tag.track_num[0]:
		tags['track'] = tag.track_num[0]
	tags['composer'] = tag.composer or tags['composer']
	tags['publisher'] = tag.publisher or tags['publisher']
	if tag.genre is not None and tag.genre.name:
		tags['genre'] = tag.genre.name
	return tags

# Lengths of songs we've already read, so each file only gets opened once
# (the playlist total adds them all up every time a song is added or removed)
song_lengths = {}

# Length of a song in seconds (0 if it can't be read)
def get_length(path):
	if path in song_lengths:
		return song_lengths[path]
	try:
		length = MP3(path).info.length
	except Exception as e:
		print('Could not read length:', e)
		length = 0
	song_lengths[path] = length
	return length

# Size the album art is shown at (pixels)
ART_SIZE = 140
# Picture files to look for in a song's folder when the MP3 has no art inside it
COVER_FILES = ['cover.jpg', 'cover.png', 'folder.jpg', 'folder.png', 'front.jpg', 'front.png', 'albumart.jpg']

# Find the album art for a song and return it as a Pillow image (None if there isn't any)
def find_album_art(path):
	# 1. Art stored inside the MP3's tags
	try:
		audio = eyed3.load(path)
		if audio is not None and audio.tag is not None and len(audio.tag.images) > 0:
			images = list(audio.tag.images)
			# Use the front cover if the file says which one it is, otherwise the first picture
			chosen = images[0]
			for image in images:
				# Picture type 3 is "front cover" in the ID3 standard
				if image.picture_type == 3:
					chosen = image
					break
			return Image.open(BytesIO(chosen.image_data))
	except Exception as e:
		print('Could not read album art from tags:', e)
	# 2. A cover picture in the same folder as the song (any upper/lower case)
	folder = os.path.dirname(path)
	try:
		files = {name.lower(): name for name in os.listdir(folder)}
	except OSError:
		files = {}
	for cover in COVER_FILES:
		if cover in files:
			try:
				return Image.open(os.path.join(folder, files[cover]))
			except Exception as e:
				print('Could not open', cover, e)
	return None

# Show a song's album art, or the music note picture if it hasn't got any
def show_album_art(path):
	img = find_album_art(path) if path else None
	if img is None:
		art = no_art_img
	else:
		# Shrink to fit the box, keeping the shape of the picture
		img = img.convert('RGB')
		img.thumbnail((ART_SIZE, ART_SIZE))
		art = ImageTk.PhotoImage(img)
	album_art_label.config(image=art)
	# Keep a reference to the picture - without this Python throws it away and the label goes blank
	album_art_label.image = art

# "never", "once" or "12 times, last Today 10:59" for the details panel
def plays_text(path):
	count = play_count(path)
	if count == 0:
		return 'never'
	times = 'once' if count == 1 else f'{count} times'
	return f'{times}, last {short_last_played(path)}'

#get the information for the selected song
def song_info(track):
	tags = read_tags(track)
	length = time.strftime('%H:%M:%S', time.gmtime(get_length(track)))
	# The title goes in big letters at the top, the rest underneath, one per line
	current_song.config(text=tags['title'])
	lines = [
		f'Artist: {tags["artist"]}',
		f'Album: {tags["album"]}',
		f'Track: {tags["track"]}    Genre: {tags["genre"]}',
		f'Duration: {length}',
		f'Played: {plays_text(track)}',
		f'Composer: {tags["composer"]}',
		f'Publisher: {tags["publisher"]}',
	]
	song_info_label.config(text='\n'.join(lines))
	show_album_art(track)

# Clicking a song in the playlist shows its info
def song_selected(event):
	index = selected_index()
	# This also fires when the selection is cleared, so check something is selected
	if index is None:
		return
	song_info(song_paths[index])

# Load and play the song at a position in the playlist - everything that plays a song uses this.
# start is how many seconds into the song to begin (0 = the beginning).
def play_song(index, start=0):
	global current_index, song_length, stopped, paused, timer_id, seek_offset, resume_index, resume_at
	global listened_seconds, play_counted
	if index is None or index < 0 or index >= len(song_paths):
		return
	path = song_paths[index]
	try:
		pygame.mixer.music.load(path)
		pygame.mixer.music.play(loops=0, start=start)
	except pygame.error as e:
		print('Could not play', path, e)
		status_bar.config(text=f"Can't play {display_name(path)}  ")
		return
	print('Play:', path)
	current_index = index
	stopped = False
	paused = False
	seek_offset = start
	# A song is playing now, so there's nothing left to carry on from
	resume_index = None
	resume_at = None
	# Start counting listening time for this song afresh (Repeat counts each time round)
	listened_seconds = 0
	play_counted = False
	visualiser.load(path)
	song_length = get_length(path)
	# Reset Slider and Status bar
	my_slider.config(to=max(int(song_length), 1), value=start)
	status_bar.config(text='')
	highlight(index)
	current_song.config(text=read_tags(path)['title'])
	song_info(path)
	# Music is playing - stop the laptop going to sleep
	keep_awake(True)
	# Make sure only one timer is running, then start it
	cancel_timer()
	timer_id = root.after(1000, play_time)

# How far through the song we are, in seconds (None when stopped or paused) - used by the visualiser
def song_position():
	if stopped or paused:
		return None
	ms = pygame.mixer.music.get_pos()
	if ms < 0:
		return None
	return seek_offset + ms / 1000

# Where we are in the playlist: the song that's loaded, otherwise the selected one
def position():
	if current_index is not None:
		return current_index
	return selected_index()

# play selected song
def play():
	if not song_paths:
		status_bar.config(text='Playlist is empty - add some songs first  ')
		return
	index = selected_index()
	if index is None:
		index = 0
	if index == resume_index and resume_at:
		# This is the song that was playing when the player was last closed - carry on from there
		play_song(index, start=resume_at)
	else:
		play_song(index)

# Space bar: play if nothing's playing, otherwise pause / resume
def play_pause():
	if stopped:
		play()
	else:
		pause()

# Forward button and end of song: next song, or a random one if Shuffle is ticked
def next_track(song_finished=False):
	if not song_paths:
		return
	# Repeat Song - when a song finishes, play it again
	# (the Forward button still moves on to the next song)
	if song_finished and repeat_mode == REPEAT_SONG:
		play_song(current_index)
		return
	if shuf.get() == 1:
		play_song(randint(0, len(song_paths) - 1))
		return
	pos = position()
	next_one = 0 if pos is None else pos + 1
	if next_one >= len(song_paths):
		# Last song in the playlist
		if repeat_mode == REPEAT_ALL:
			# Go back to the start of the playlist
			play_song(0)
			return
		if song_finished:
			stop()
			status_bar.config(text='End of playlist  ')
		return
	play_song(next_one)

# Play previous song in playlist (restarts the song if it's the first one)
def previous_song():
	if not song_paths:
		return
	pos = position()
	play_song(max(0, pos - 1) if pos is not None else 0)

# Stop playing current song
# ---------------- Keeping the computer awake ----------------
# Without this, Windows puts the laptop to sleep after a while and the music stops.
# While a song is playing we tell Windows "the system is needed" - it stays awake but the
# screen can still switch off as normal. When the music is paused or stopped we take that
# back, so the laptop can sleep again.
# (Closing the laptop's lid still sends it to sleep - that's a Windows power setting.)
# Only Windows needs this - on the Pi it does nothing.
ES_CONTINUOUS = 0x80000000        # keep this setting until we change it
ES_SYSTEM_REQUIRED = 0x00000001   # don't go to sleep (the screen is still allowed to turn off)
keeping_awake = False

def keep_awake(on):
	global keeping_awake
	if on == keeping_awake:
		# Already set this way
		return
	keeping_awake = on
	if sys.platform != 'win32':
		return
	if on:
		flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
	else:
		# ES_CONTINUOUS on its own clears the request, so normal sleep settings apply again
		flags = ES_CONTINUOUS
	try:
		ctypes.windll.kernel32.SetThreadExecutionState(flags)
	except Exception as e:
		print('Could not change the sleep setting:', e)

def stop():
	global stopped, paused
	cancel_timer()
	pygame.mixer.music.stop()
	stopped = True
	paused = False
	# Nothing playing, so the laptop can go to sleep again
	keep_awake(False)
	# Reset Slider and Status bar
	my_slider.config(value=0)
	status_bar.config(text='STOP')

# Repeat modes - the Repeat button cycles Off -> Repeat Song -> Repeat All -> Off
REPEAT_OFF = 0
REPEAT_SONG = 1
REPEAT_ALL = 2
repeat_labels = ['Repeat: Off', 'Repeat: Song', 'Repeat: All']
repeat_mode = REPEAT_OFF

def toggle_repeat():
	global repeat_mode
	repeat_mode = (repeat_mode + 1) % 3
	repeat_button.config(image=repeat_imgs[repeat_mode])

# Pause and unpause song
def pause():
	global paused
	if stopped:
		return
	if paused:
		pygame.mixer.music.unpause()
		paused = False
		keep_awake(True)
	else:
		pygame.mixer.music.pause()
		paused = True
		# Paused - let the laptop sleep if it's left like this
		keep_awake(False)

# Dragging the slider jumps to that point in the song
def slide(x):
	global paused, seek_offset
	if stopped or current_index is None:
		return
	seek_offset = int(my_slider.get())
	pygame.mixer.music.play(loops=0, start=seek_offset)
	paused = False
	keep_awake(True)

# Skip buttons - jump back (-10) or forward (+10) seconds in the song
SKIP_SECONDS = 10

def skip(seconds):
	global seek_offset
	if stopped or current_index is None:
		return
	new_time = int(my_slider.get()) + seconds
	if new_time >= int(song_length):
		# Skipped past the end - move on as if the song had finished
		next_track(song_finished=True)
		return
	new_time = max(0, new_time)
	seek_offset = new_time
	pygame.mixer.music.play(loops=0, start=new_time)
	if paused:
		# Stay paused if we were paused - it just waits at the new point
		pygame.mixer.music.pause()
	my_slider.config(value=new_time)
	converted_time = time.strftime('%H:%M:%S', time.gmtime(new_time))
	converted_length = time.strftime('%H:%M:%S', time.gmtime(song_length))
	status_bar.config(text=f'Time Elapsed: {converted_time} of {converted_length}  ')

def skip_back():
	skip(-SKIP_SECONDS)

def skip_forward():
	skip(SKIP_SECONDS)

# Set the sound level from the volume slider and the Mute button
def apply_volume():
	level = float(volume_slider.get())
	if muted:
		pygame.mixer.music.set_volume(0)
		volume_level.config(text='Muted')
		mute_button.config(image=mute_on_img)
	else:
		pygame.mixer.music.set_volume(level)
		# Show the volume as a percentage under the slider
		volume_level.config(text=f'{round(level * 100)}%')
		mute_button.config(image=mute_off_img)

# Moving the volume slider - this also turns Mute off, so you hear the change
def volume(x):
	global muted
	muted = False
	apply_volume()

# Mute button (and the M key) - switches the sound off and on again
def toggle_mute():
	global muted
	muted = not muted
	apply_volume()

# Up/Down keys - turn the volume up or down a step
VOLUME_STEP = 0.05

def change_volume(step):
	level = float(volume_slider.get()) + step
	# Keep it between 0 and 1
	level = min(1.0, max(0.0, level))
	volume_slider.config(value=level)
	volume(None)

def volume_up():
	change_volume(VOLUME_STEP)

def volume_down():
	change_volume(-VOLUME_STEP)

# Shuffle button switches between Off and On, like the Repeat button
def toggle_shuffle():
	if shuf.get() == 1:
		shuf.set(0)
		shuffle_button.config(image=shuffle_off_img)
	else:
		shuf.set(1)
		shuffle_button.config(image=shuffle_on_img)

# ---------------- Playlists ----------------
# Playlists are saved as .m3u files - a plain text file with one song per line.
# VLC, Windows Media Player and most other players can open them too.

# Show the playlist name in the window title, with a * if it has unsaved changes
def update_title():
	name = display_name(playlist_file) if playlist_file else 'New Playlist'
	star = ' *' if playlist_changed else ''
	root.title(f'My MP3 - {name}{star}')
	# The playlist's name also goes at the top of the playlist
	playlist_header.config(text=f'Playlist: {name}{star}')

def mark_changed():
	global playlist_changed, resume_index, resume_at, sort_column
	playlist_changed = True
	# Songs may have moved, so forget about carrying on from where the player was last closed
	resume_index = None
	resume_at = None
	# ...and the playlist may not be in sorted order any more, so take the arrow off the heading
	if sort_column is not None:
		sort_column = None
		show_sort_arrow()
	update_title()

# Before throwing the current playlist away, offer to save it.
# Returns True if it's OK to carry on, False if the user pressed Cancel.
def ok_to_discard():
	if not playlist_changed or not song_paths:
		return True
	answer = messagebox.askyesnocancel('Save Playlist', 'Save changes to the playlist first?')
	if answer is None:
		# Cancel
		return False
	if answer:
		# Yes - only carry on if it actually got saved
		return save_playlist()
	# No - carry on without saving
	return True

# Write the playlist to a file
def write_playlist(path):
	with open(path, 'w', encoding='utf-8') as f:
		f.write('#EXTM3U\n')
		for song in song_paths:
			tags = read_tags(song)
			# #EXTINF holds the length and name so other players can show them without reading the song
			f.write(f'#EXTINF:{int(get_length(song))},{tags["artist"]} - {tags["title"]}\n')
			f.write(song + '\n')

# Save As - always asks for a file name
def save_playlist_as():
	global playlist_file, playlist_changed
	if not song_paths:
		status_bar.config(text='Playlist is empty - nothing to save  ')
		return False
	path = filedialog.asksaveasfilename(initialdir=playlist_start_folder(), title='Save Playlist As', defaultextension='.m3u', filetypes=(('Playlists', '*.m3u *.m3u8'), ))
	# Pressing Cancel returns an empty string
	if not path:
		return False
	try:
		write_playlist(path)
	except OSError as e:
		messagebox.showerror('Save Playlist', f"Couldn't save the playlist:\n{e}")
		return False
	playlist_file = path
	playlist_changed = False
	update_title()
	status_bar.config(text=f'Saved {display_name(path)}  ')
	return True

# Save - uses the current file name, or asks for one if it's a new playlist
def save_playlist():
	global playlist_changed
	if playlist_file is None:
		return save_playlist_as()
	if not song_paths:
		status_bar.config(text='Playlist is empty - nothing to save  ')
		return False
	try:
		write_playlist(playlist_file)
	except OSError as e:
		messagebox.showerror('Save Playlist', f"Couldn't save the playlist:\n{e}")
		return False
	playlist_changed = False
	update_title()
	status_bar.config(text=f'Saved {display_name(playlist_file)}  ')
	return True

# Read the song paths out of a playlist file
def read_playlist(path):
	folder = os.path.dirname(path)
	songs = []
	missing = 0
	# utf-8-sig copes with files saved by Windows programs that add a marker at the start
	with open(path, 'r', encoding='utf-8-sig', errors='replace') as f:
		for line in f:
			line = line.strip()
			# Skip blank lines and #comment lines like #EXTM3U and #EXTINF
			if not line or line.startswith('#'):
				continue
			# Playlists made by other programs sometimes use paths relative to the playlist's folder
			if not os.path.isabs(line):
				line = os.path.join(folder, line)
			line = os.path.normpath(line)
			if os.path.isfile(line):
				songs.append(line)
			else:
				print('Missing from playlist:', line)
				missing += 1
	return songs, missing

# Load a playlist file - replaces the songs that are in the list now.
# Used by Open Playlist and when the player starts up. Returns how many songs couldn't be found.
def load_playlist(path):
	global playlist_file, playlist_changed, current_index
	# read_playlist can fail with OSError - whoever calls this deals with that
	songs, missing = read_playlist(path)
	# Empty the current list, then fill it from the file
	stop()
	clear_rows()
	song_paths.clear()
	current_index = None
	clear_song_labels()
	for song in songs:
		add_to_playlist(song)
	update_summary()
	playlist_file = path
	# Songs that couldn't be found are dropped, so the playlist has changed from what's in the file
	playlist_changed = missing > 0
	update_title()
	if missing:
		status_bar.config(text=f'Opened {display_name(path)} - {missing} song(s) could not be found  ')
	else:
		status_bar.config(text=f'Opened {display_name(path)} - {len(songs)} songs  ')
	return missing

# Open a playlist - asks which file, then loads it
def open_playlist():
	if not ok_to_discard():
		return
	path = filedialog.askopenfilename(initialdir=playlist_start_folder(), title='Open Playlist', filetypes=(('Playlists', '*.m3u *.m3u8'), ))
	if not path:
		return
	try:
		load_playlist(path)
	except OSError as e:
		messagebox.showerror('Open Playlist', f"Couldn't open the playlist:\n{e}")

# Start a new, empty playlist
def new_playlist():
	global playlist_file, playlist_changed
	if not ok_to_discard():
		return
	delete_all_songs()
	playlist_file = None
	playlist_changed = False
	update_title()

# ---------------- Adding a song to another playlist ----------------
# Right-click a song (or use the Add to Playlist button) to put it into a different
# saved playlist. The song is added to the end of that playlist's file - the playlist
# that's open stays as it is, and whatever's playing carries on.

# The saved playlists in the playlist folder (File > Settings), sorted by name.
# If no playlist folder is set, it uses the folder of the playlist that's open.
def saved_playlists():
	folder = setting_folder('playlist_folder')
	if folder is None and playlist_file:
		folder = os.path.dirname(playlist_file)
	if folder is None:
		return []
	found = []
	try:
		names = os.listdir(folder)
	except OSError as e:
		print('Could not look in the playlist folder:', e)
		return []
	for name in names:
		if name.lower().endswith(('.m3u', '.m3u8')):
			found.append(os.path.join(folder, name))
	# Sort by name, ignoring upper/lower case
	found.sort(key=lambda path: display_name(path).lower())
	return found

# True if two paths are the same file (written the same way once tidied)
def same_file(path1, path2):
	return tidy_path(path1) == tidy_path(path2)

# Add one song to the end of a playlist file. Returns True if it was added,
# False if it was already in it. Can fail with OSError - whoever calls this deals with that.
def append_to_playlist_file(song, playlist):
	if os.path.isfile(playlist):
		songs_in_it, missing = read_playlist(playlist)
		for other in songs_in_it:
			if same_file(other, song):
				return False
		# Make sure the file ends with a new line before adding to it
		with open(playlist, 'rb') as f:
			data = f.read()
		start = '' if data == b'' or data.endswith(b'\n') else '\n'
	else:
		start = '#EXTM3U\n'
	tags = read_tags(song)
	# 'a' = append: add to the end without touching what's already there
	with open(playlist, 'a', encoding='utf-8') as f:
		f.write(start)
		f.write(f'#EXTINF:{int(get_length(song))},{tags["artist"]} - {tags["title"]}\n')
		f.write(song + '\n')
	return True

# Add the selected song to the playlist file chosen from the menu
def add_selected_to(playlist):
	index = selected_index()
	if index is None:
		status_bar.config(text='Select a song first  ')
		return
	song = song_paths[index]
	title = read_tags(song)['title']
	name = display_name(playlist)
	if playlist_file and same_file(playlist, playlist_file):
		status_bar.config(text=f'{title} is already in {name} - it is the playlist that is open  ')
		return
	try:
		added = append_to_playlist_file(song, playlist)
	except OSError as e:
		messagebox.showerror('Add to Playlist', f"Couldn't add the song to {name}:\n{e}")
		return
	if added:
		status_bar.config(text=f'Added {title} to {name}  ')
	else:
		status_bar.config(text=f'{title} is already in {name}  ')

# "Other playlist..." - pick any playlist file
def add_selected_to_other():
	if selected_index() is None:
		status_bar.config(text='Select a song first  ')
		return
	path = filedialog.askopenfilename(initialdir=playlist_start_folder(), title='Add Song to Playlist', filetypes=(('Playlists', '*.m3u *.m3u8'), ))
	if path:
		add_selected_to(path)

# "New playlist..." - type a name for a new playlist with this song in it.
# If you pick a playlist that already exists, the song is added to it rather than replacing it.
def add_selected_to_new():
	if selected_index() is None:
		status_bar.config(text='Select a song first  ')
		return
	path = filedialog.asksaveasfilename(initialdir=playlist_start_folder(), title='New Playlist for this Song', defaultextension='.m3u', filetypes=(('Playlists', '*.m3u *.m3u8'), ), confirmoverwrite=False)
	if path:
		add_selected_to(path)

# Fill an "Add to playlist" menu with the saved playlists. It's rebuilt every time the
# menu opens, so a playlist saved a minute ago is in the list.
def fill_add_menu(menu):
	menu.delete(0, END)
	playlists = saved_playlists()
	if not playlists:
		menu.add_command(label='(no saved playlists in the playlist folder)', state=DISABLED)
	for path in playlists:
		if playlist_file and same_file(path, playlist_file):
			# The playlist that's open - the song is already in it
			menu.add_command(label=f'{display_name(path)}  (open now)', state=DISABLED)
		else:
			# 'path=path' makes each menu item remember its own playlist
			menu.add_command(label=display_name(path), command=lambda path=path: add_selected_to(path))
	menu.add_separator()
	menu.add_command(label='Other playlist...', command=add_selected_to_other)
	menu.add_command(label='New playlist...', command=add_selected_to_new)

# Make an "Add to playlist" menu that fills itself each time it opens
def make_add_menu(parent):
	menu = Menu(parent, tearoff=0)
	menu.config(postcommand=lambda: fill_add_menu(menu))
	return menu

# Move the selected song up (-1) or down (+1) the playlist
def move_song(direction):
	global current_index
	index = selected_index()
	if index is None:
		return
	new_index = index + direction
	if new_index < 0 or new_index >= len(song_paths):
		# Already at the top or bottom
		return
	# Swap the two songs in the list of paths...
	song_paths[index], song_paths[new_index] = song_paths[new_index], song_paths[index]
	# ...and redo the table so the rows and their numbers match
	refresh_playlist()
	# Keep track of the playing song if it was one of the two that swapped
	if current_index == index:
		current_index = new_index
	elif current_index == new_index:
		current_index = index
	highlight(new_index)
	mark_changed()

def move_up():
	move_song(-1)

def move_down():
	move_song(1)

# File > Settings - pick a folder and remember it
def choose_folder(key, title):
	current = setting_folder(key) or os.path.expanduser('~')
	folder = filedialog.askdirectory(initialdir=current, title=title, mustexist=True)
	# Pressing Cancel returns an empty string (or an empty tuple on some systems)
	if not folder:
		return
	settings[key] = folder
	save_settings()
	status_bar.config(text=f'{title}: {folder}  ')

def set_music_folder():
	choose_folder('music_folder', 'Music Folder')

def set_playlist_folder():
	choose_folder('playlist_folder', 'Playlist Folder')

# ---------------- Remembering where you were ----------------

# Called when the player closes - write the volume, playlist and song position to settings.json
def remember_state():
	settings['volume'] = float(volume_slider.get())
	settings['muted'] = muted
	settings['shuffle'] = shuf.get() == 1
	settings['repeat'] = repeat_mode
	settings['last_playlist'] = playlist_file or ''
	# Only remember the song if the playlist on disk matches what's on screen
	# (if it has unsaved changes, the song numbers in the file could be different)
	if playlist_file and not playlist_changed and current_index is not None:
		settings['last_song'] = current_index
		settings['last_position'] = 0 if stopped else int(my_slider.get())
	else:
		settings['last_song'] = -1
		settings['last_position'] = 0
	save_settings()

# Called once when the player starts - put things back the way they were left
def restore_state():
	global muted, repeat_mode, resume_index, resume_at
	# Volume and Mute
	volume_slider.config(value=settings['volume'])
	muted = settings['muted']
	apply_volume()
	# Shuffle
	if settings['shuffle']:
		shuf.set(1)
		shuffle_button.config(image=shuffle_on_img)
	# Repeat (ignore anything that isn't one of the three modes)
	if settings['repeat'] in (REPEAT_OFF, REPEAT_SONG, REPEAT_ALL):
		repeat_mode = settings['repeat']
		repeat_button.config(image=repeat_imgs[repeat_mode])
	# The playlist that was open - if the file is still there
	path = settings['last_playlist']
	if not path or not os.path.isfile(path):
		return
	try:
		missing = load_playlist(path)
	except OSError as e:
		print('Could not reopen the last playlist:', e)
		return
	# If songs have gone missing the numbers have shifted, so don't try to find the last song
	song = settings['last_song']
	if missing or song < 0 or song >= len(song_paths):
		return
	# Select the song and show its details, ready for Play
	highlight(song)
	current_song.config(text=read_tags(song_paths[song])['title'])
	song_info(song_paths[song])
	seconds = settings['last_position']
	if 0 < seconds < get_length(song_paths[song]):
		resume_index = song
		resume_at = seconds
		converted = time.strftime('%H:%M:%S', time.gmtime(seconds))
		status_bar.config(text=f'Press Play to carry on from {converted}  ')

# Closing the window or pressing Exit - offer to save first
def exit_player():
	if ok_to_discard():
		remember_state()
		keep_awake(False)
		root.quit()

# Help > Keyboard Shortcuts
SHORTCUTS_TEXT = '''Space\tPlay / Pause
Enter\tPlay the selected song
Left / Right\tBack / Forward 10 seconds
Ctrl+Left / Ctrl+Right\tPrevious / Next song
Up / Down\tVolume up / down
M\tMute / Unmute
Ctrl+O\tOpen playlist
Ctrl+S\tSave playlist'''

def show_shortcuts():
	messagebox.showinfo('Keyboard Shortcuts', SHORTCUTS_TEXT)

# Create Menu Bar and cascades
my_menu = Menu(root)
root.config(menu=my_menu)
#add file menu
file_menu = Menu(my_menu)
my_menu.add_cascade(label="File", menu=file_menu)
settings_menu = Menu(file_menu)
file_menu.add_cascade(label="Settings", menu=settings_menu)
settings_menu.add_command(label="Set Music Folder...", command=set_music_folder)
settings_menu.add_command(label="Set Playlist Folder...", command=set_playlist_folder)
file_menu.add_separator()
file_menu.add_command(label="Exit...", command=exit_player)
# Playlist menu - save and open playlists
playlist_menu = Menu(my_menu)
my_menu.add_cascade(label="Playlist", menu=playlist_menu)
playlist_menu.add_command(label="New Playlist", command=new_playlist)
playlist_menu.add_command(label="Open Playlist...", command=open_playlist, accelerator="Ctrl+O")
playlist_menu.add_command(label="Save Playlist", command=save_playlist, accelerator="Ctrl+S")
playlist_menu.add_command(label="Save Playlist As...", command=save_playlist_as)
playlist_menu.add_separator()
playlist_menu.add_command(label="Move Song Up", command=move_up)
playlist_menu.add_command(label="Move Song Down", command=move_down)
playlist_menu.add_cascade(label="Add Song to Another Playlist", menu=make_add_menu(playlist_menu))
#add Song Menu
add_song_menu = Menu(my_menu)
my_menu.add_cascade(label="Add Songs", menu=add_song_menu)
add_song_menu.add_command(label="Add one Song to playlist", command=add_song)
# Add Multiple songs to playlist
add_song_menu.add_command(label="Add multiple Songs to playlist", command=add_multiple)
# Create Delete Song Menu
remove_song_menu = Menu(my_menu)
my_menu.add_cascade(label="Remove Songs", menu=remove_song_menu)
remove_song_menu.add_command(label="Delete a song from playlist", command=delete_song)
remove_song_menu.add_command(label="Delete all songs from playlist", command=delete_all_songs)
# Help menu
help_menu = Menu(my_menu)
my_menu.add_cascade(label="Help", menu=help_menu)
help_menu.add_command(label="Keyboard Shortcuts", command=show_shortcuts)

# ---------------- The window ----------------
# Layout, top to bottom:
#   title banner
#   now playing strip: album art + song details on the left, visualiser on the right
#   playlist: name and total at the top, the table of songs, Move Up / Move Down underneath
#   position slider
#   control buttons on the left, volume (mute, slider, level) on the right
#   status bar with a small Exit button

GREEN = '#00e000'     # same green as the buttons drawn by make_icons.py
PANEL = 'black'       # background of the black panels

# Title banner - black with green text and a green edge, to match the buttons
title_label = Label(root, text="MAC's MEGA MIXES", font=("Helvetica", 24, "bold"), bg=PANEL, fg=GREEN,
	highlightthickness=2, highlightbackground=GREEN, highlightcolor=GREEN, pady=4)
title_label.pack(fill=X, padx=14, pady=(10, 8))

# ----- Now playing strip -----
top_frame = Frame(root)
top_frame.pack(fill=X, padx=14)

info_frame = Frame(top_frame, bg=PANEL, relief=RAISED, bd=1)
info_frame.pack(side=LEFT, fill=Y)
# Music note picture, shown when a song has no album art (enlarged to fill the art box)
no_art_img = ImageTk.PhotoImage(Image.open(os.path.join(script_dir, 'icons', '1486505261-eighth-eighth-note-multimedia-player-music-note_81397.png')).convert('RGBA').resize((ART_SIZE, ART_SIZE)))
album_art_label = Label(info_frame, image=no_art_img, bg=PANEL, width=ART_SIZE, height=ART_SIZE)
album_art_label.image = no_art_img
album_art_label.grid(row=0, column=0, rowspan=2, padx=8, pady=8)
# Name of the song that's playing, in big letters above its details
current_song = Label(info_frame, text="", bg=PANEL, fg=GREEN, font=("Helvetica", 15, "bold"), width=22, anchor=W)
current_song.grid(row=0, column=1, sticky=W, padx=(0, 8), pady=(8, 0))
song_info_label = Label(info_frame, text="No Song Selected", bg=PANEL, fg=GREEN, width=30, justify=LEFT, anchor=NW)
song_info_label.grid(row=1, column=1, sticky=NW, padx=(0, 8), pady=(2, 8))

# Music visualiser - bars that bounce along to the song - fills the rest of the strip
visualiser = Visualiser(top_frame, song_position, width=470, height=ART_SIZE + 16)
visualiser.pack(side=RIGHT, padx=(10, 0))

# ----- Status bar (packed now so it always stays at the very bottom) -----
status_frame = Frame(root, bd=1, relief=GROOVE)
status_frame.pack(fill=X, side=BOTTOM)
# Small Exit button at the left of the status bar (File > Exit does the same)
button_quit = Button(status_frame, text="Exit", bg="red", fg="white", activebackground="#c00000", font=("Helvetica", 10, "bold"), padx=10, pady=0, command=exit_player)
button_quit.pack(side=LEFT, padx=4, pady=2)
Tooltip(button_quit, 'Close the player')
status_bar = Label(status_frame, text="", anchor=E)
status_bar.pack(side=RIGHT, fill=X, expand=True, padx=4)

# ----- Controls and volume -----
controls_row = Frame(root)
controls_row.pack(side=BOTTOM, fill=X, padx=14, pady=(0, 8))
control_frame = Frame(controls_row)
control_frame.pack(side=LEFT)

# Images for the control buttons - all drawn by make_icons.py so they match
def button_image(name):
	return PhotoImage(file=os.path.join(script_dir, 'icons', f'btn_{name}.png'))

previous_img = button_image('previous')
back10_img = button_image('back10')
play_img = button_image('play')
pause_img = button_image('pause')
stop_img = button_image('stop')
forward10_img = button_image('forward10')
next_img = button_image('next')
shuffle_off_img = button_image('shuffle_off')
shuffle_on_img = button_image('shuffle_on')
# In the same order as REPEAT_OFF, REPEAT_SONG, REPEAT_ALL
repeat_imgs = [button_image('repeat_off'), button_image('repeat_song'), button_image('repeat_all')]

#global shuf to set shuffle status as a int Variable
shuf = IntVar()

# All the control buttons on one line, left to right, each with its tooltip
# (the tooltip text can be a function so Shuffle and Repeat say what they're set to now)
buttons = [
	(previous_img, previous_song, 'Previous song'),
	(back10_img, skip_back, f'Back {SKIP_SECONDS} seconds'),
	(play_img, play, 'Play'),
	(pause_img, pause, 'Pause / Resume'),
	(stop_img, stop, 'Stop'),
	(forward10_img, skip_forward, f'Forward {SKIP_SECONDS} seconds'),
	(next_img, next_track, 'Next song'),
	(shuffle_off_img, toggle_shuffle, lambda: 'Shuffle: On' if shuf.get() == 1 else 'Shuffle: Off'),
	(repeat_imgs[repeat_mode], toggle_repeat, lambda: repeat_labels[repeat_mode]),
]
made = []
for column, (image, action, tip) in enumerate(buttons):
	button = Button(control_frame, image=image, borderwidth=0, highlightthickness=0, command=action)
	# Stop a grey square appearing behind the button when the mouse is over it
	button.config(activebackground=button.cget('background'))
	# A bigger gap before Shuffle and Repeat to set them apart from the playing controls
	button.grid(row=0, column=column, padx=(14 if column == 7 else 3, 3))
	Tooltip(button, tip)
	made.append(button)
(back_button, back10_button, play_button, pause_button, stop_button,
	forward10_button, forward_button, shuffle_button, repeat_button) = made

# Volume - a long slider across to the right of the buttons.
# Left is quiet and right is loud, with the Mute button at the start.
volume_frame = Frame(controls_row)
volume_frame.pack(side=RIGHT)
mute_off_img = button_image('mute_off')
mute_on_img = button_image('mute_on')
mute_button = Button(volume_frame, image=mute_off_img, borderwidth=0, highlightthickness=0, command=toggle_mute)
mute_button.config(activebackground=mute_button.cget('background'))
mute_button.pack(side=LEFT, padx=(0, 6))
Tooltip(mute_button, lambda: 'Unmute' if muted else 'Mute')
vol_down_img = button_image('volume_down')
vol_up_img = button_image('volume_up')
vol_down_label = Label(volume_frame, image=vol_down_img)
vol_down_label.pack(side=LEFT)
volume_slider = ttk.Scale(volume_frame, from_=0, to=1, orient=HORIZONTAL, value=1, command=volume, length=150)
volume_slider.pack(side=LEFT, padx=4)
vol_up_label = Label(volume_frame, image=vol_up_img)
vol_up_label.pack(side=LEFT)
# Current volume as a percentage (says "Muted" when muted)
volume_level = Label(volume_frame, text='100%', width=6)
volume_level.pack(side=LEFT, padx=(4, 0))
Tooltip(volume_slider, lambda: f'Volume {volume_level.cget("text")}')

# Music Position Slider - right across the window, just above the buttons
my_slider = ttk.Scale(root, from_=0, to=100, orient=HORIZONTAL, value=0, command=slide)
my_slider.pack(side=BOTTOM, fill=X, padx=14, pady=(4, 8))

# ----- Playlist - fills all the space that's left in the middle -----
playlist_frame = Frame(root, bg=PANEL, relief=RAISED, bd=1)
playlist_frame.pack(fill=BOTH, expand=True, padx=14, pady=(10, 0))

# Header: playlist name on the left, number of songs and total time on the right
header_frame = Frame(playlist_frame, bg='#101010')
header_frame.pack(fill=X)
playlist_header = Label(header_frame, text='Playlist: New Playlist', bg='#101010', fg=GREEN, font=("Helvetica", 13, "bold"), anchor=W)
playlist_header.pack(side=LEFT, padx=8, pady=4)
playlist_summary = Label(header_frame, text='No songs', bg='#101010', fg=GREEN)
playlist_summary.pack(side=RIGHT, padx=8)

# The table of songs. Colours are set with a ttk Style:
# black with green writing, and the selected (playing) song in red like before.
style = ttk.Style()
# The 'clam' look lets us colour the column headings too
style.theme_use('clam')
style.configure('Playlist.Treeview', background=PANEL, fieldbackground=PANEL, foreground=GREEN, rowheight=22, borderwidth=0)
style.map('Playlist.Treeview', background=[('selected', 'red')], foreground=[('selected', 'black')])
style.configure('Playlist.Treeview.Heading', background='#1c1c1c', foreground='#d0d0d0', font=("Helvetica", 10, "bold"), relief=FLAT)
style.map('Playlist.Treeview.Heading', background=[('active', '#333333')])

table_frame = Frame(playlist_frame, bg=PANEL)
table_frame.pack(fill=BOTH, expand=True)
scroll_song_display = ttk.Scrollbar(table_frame, orient=VERTICAL)
song_display = ttk.Treeview(table_frame, columns=PLAYLIST_COLUMNS, show='headings', selectmode='browse', style='Playlist.Treeview', yscrollcommand=scroll_song_display.set)
scroll_song_display.config(command=song_display.yview)
scroll_song_display.pack(side=RIGHT, fill=Y)
song_display.pack(side=LEFT, fill=BOTH, expand=True)
# Column widths - Title, Artist and Album stretch when the window gets wider
song_display.column('num', width=40, minwidth=40, stretch=False, anchor=E)
song_display.column('title', width=220, minwidth=100)
song_display.column('artist', width=150, minwidth=80)
song_display.column('album', width=150, minwidth=80)
song_display.column('time', width=55, minwidth=55, stretch=False, anchor=E)
song_display.column('plays', width=50, minwidth=50, stretch=False, anchor=E)
song_display.column('last', width=120, minwidth=100, stretch=False, anchor=E)
song_display.bind("<<TreeviewSelect>>", song_selected)
# Double-click a song to play it
song_display.bind("<Double-Button-1>", lambda event: play())
show_sort_arrow()

# Move Up / Move Down buttons under the playlist
move_frame = Frame(playlist_frame, bg=PANEL)
move_frame.pack(fill=X, pady=4)
move_up_button = Button(move_frame, text='Move Up', width=10, command=move_up)
move_up_button.pack(side=LEFT, padx=(8, 5))
move_down_button = Button(move_frame, text='Move Down', width=10, command=move_down)
move_down_button.pack(side=LEFT, padx=5)
Tooltip(move_up_button, 'Move the selected song up the playlist')
Tooltip(move_down_button, 'Move the selected song down the playlist')

# Add to Playlist button - opens the list of playlists just under the button
button_add_menu = make_add_menu(root)

def show_add_menu():
	x = add_to_button.winfo_rootx()
	y = add_to_button.winfo_rooty() + add_to_button.winfo_height()
	button_add_menu.tk_popup(x, y)

add_to_button = Button(move_frame, text='Add to Playlist...', command=show_add_menu)
add_to_button.pack(side=LEFT, padx=(15, 5))
Tooltip(add_to_button, 'Add the selected song to another playlist')

# Right-click menu for the songs in the playlist
song_menu = Menu(root, tearoff=0)
song_menu.add_command(label='Play', command=play)
song_menu.add_cascade(label='Add to playlist', menu=make_add_menu(song_menu))
song_menu.add_separator()
song_menu.add_command(label='Move Up', command=move_up)
song_menu.add_command(label='Move Down', command=move_down)
song_menu.add_separator()
song_menu.add_command(label='Delete from this playlist', command=delete_song)

# Right-clicking a song selects it first, then shows the menu where the mouse is
def right_click(event):
	row = song_display.identify_row(event.y)
	if not row:
		# Clicked below the last song
		return
	highlight(int(row))
	song_menu.tk_popup(event.x_root, event.y_root)

song_display.bind('<Button-3>', right_click)
sort_hint = Label(move_frame, text='Click a column heading to sort', bg=PANEL, fg='#909090')
sort_hint.pack(side=RIGHT, padx=8)

# ---------------- Keyboard shortcuts ----------------
# Buttons and sliders mustn't take the keyboard focus, otherwise pressing Space on a
# focused button would click it as well as doing the shortcut
for widget in made + [move_up_button, move_down_button, add_to_button, mute_button, button_quit, my_slider, volume_slider]:
	widget.config(takefocus=0)

# Set up one shortcut key. It's bound to the playlist as well as the window, because the
# playlist normally uses the arrow keys to move the red bar - 'break' stops it doing that too.
def bind_key(key, action):
	def handler(event):
		action()
		return 'break'
	root.bind(key, handler)
	song_display.bind(key, handler)

bind_key('<space>', play_pause)
bind_key('<Return>', play)
bind_key('<Left>', skip_back)
bind_key('<Right>', skip_forward)
bind_key('<Control-Left>', previous_song)
bind_key('<Control-Right>', next_track)
bind_key('<Up>', volume_up)
bind_key('<Down>', volume_down)
bind_key('<Key-m>', toggle_mute)
bind_key('<Key-M>', toggle_mute)
root.bind('<Control-s>', lambda event: save_playlist())
root.bind('<Control-o>', lambda event: open_playlist())
# The window's close (X) button
root.protocol('WM_DELETE_WINDOW', exit_player)
# Start with the playlist ready for the keyboard
song_display.focus_set()

update_title()
restore_state()

root.mainloop()

'''Notes

Note added to check
'''
