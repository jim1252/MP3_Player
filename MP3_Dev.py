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
from visualiser import Visualiser
from tooltip import Tooltip

root = Tk()
root.title('My MP3')
root.geometry("800x850")
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
}

def load_settings():
	try:
		with open(settings_file, 'r', encoding='utf-8') as f:
			saved = json.load(f)
		# Only take settings we know about, so an old or hand-edited file can't break anything
		for key in settings:
			if isinstance(saved.get(key), str):
				settings[key] = saved[key]
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

# Turn a full path into the name shown in the playlist
def display_name(path):
	return os.path.splitext(os.path.basename(path))[0]

# Add one file to the playlist (used by both add functions)
def add_to_playlist(path):
	global last_folder
	song_paths.append(path)
	mark_changed()
	song_display.insert(END, display_name(path))
	last_folder = os.path.dirname(path)
	# If nothing is selected yet, select the first song
	if not song_display.curselection():
		song_display.select_set(0)

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
	selected = song_display.curselection()
	if not selected:
		return
	index = selected[0]
	if index == current_index:
		# Deleting the song that's playing - stop it
		stop()
		current_index = None
		clear_song_labels()
	elif current_index is not None and index < current_index:
		# A song above the playing one has gone, so it moves up one place
		current_index -= 1
	song_display.delete(index)
	del song_paths[index]
	mark_changed()
	if song_paths:
		highlight(current_index if current_index is not None else min(index, len(song_paths) - 1))

# Delete all songs from playlist
def delete_all_songs():
	global current_index
	stop()
	if song_paths:
		mark_changed()
	song_display.delete(0, END)
	song_paths.clear()
	current_index = None
	clear_song_labels()

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
	song_display.selection_clear(0, END)
	song_display.activate(index)
	song_display.selection_set(index)
	song_display.see(index)

# Read the tags from a song, falling back to sensible values if any are missing
def read_tags(path):
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

# Length of a song in seconds (0 if it can't be read)
def get_length(path):
	try:
		return MP3(path).info.length
	except Exception as e:
		print('Could not read length:', e)
		return 0

# Size the album art is shown at (pixels)
ART_SIZE = 160
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

#get the information for the selected song
def song_info(track):
	tags = read_tags(track)
	length = time.strftime('%H:%M:%S', time.gmtime(get_length(track)))
	nl = '\n'
	song_info_label.config(text=f'******* {nl} Title: {tags["title"]} {nl} Duration: {length} {nl} Artist: {tags["artist"]} {nl} Album: {tags["album"]} {nl} Track: {tags["track"]} {nl} Composer: {tags["composer"]} {nl} Publisher: {tags["publisher"]} {nl} Genre: {tags["genre"]} {nl} *******')
	show_album_art(track)

# Clicking a song in the playlist shows its info
def song_selected(event):
	selected = song_display.curselection()
	# This also fires when the selection is cleared, so check something is selected
	if not selected:
		return
	song_info(song_paths[selected[0]])

# Load and play the song at a position in the playlist - everything that plays a song uses this
def play_song(index):
	global current_index, song_length, stopped, paused, timer_id, seek_offset
	if index is None or index < 0 or index >= len(song_paths):
		return
	path = song_paths[index]
	try:
		pygame.mixer.music.load(path)
		pygame.mixer.music.play(loops=0)
	except pygame.error as e:
		print('Could not play', path, e)
		status_bar.config(text=f"Can't play {display_name(path)}  ")
		return
	print('Play:', path)
	current_index = index
	stopped = False
	paused = False
	seek_offset = 0
	visualiser.load(path)
	song_length = get_length(path)
	# Reset Slider and Status bar
	my_slider.config(to=max(int(song_length), 1), value=0)
	status_bar.config(text='')
	highlight(index)
	current_song.config(text=read_tags(path)['title'])
	song_info(path)
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
	selected = song_display.curselection()
	if selected:
		return selected[0]
	return None

# play selected song
def play():
	if not song_paths:
		status_bar.config(text='Playlist is empty - add some songs first  ')
		return
	selected = song_display.curselection()
	play_song(selected[0] if selected else 0)

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
def stop():
	global stopped, paused
	cancel_timer()
	pygame.mixer.music.stop()
	stopped = True
	paused = False
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
	else:
		pygame.mixer.music.pause()
		paused = True

# Dragging the slider jumps to that point in the song
def slide(x):
	global paused, seek_offset
	if stopped or current_index is None:
		return
	seek_offset = int(my_slider.get())
	pygame.mixer.music.play(loops=0, start=seek_offset)
	paused = False

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

def volume(x):
	level = float(volume_slider.get())
	pygame.mixer.music.set_volume(level)
	# Show the volume as a percentage under the slider
	volume_level.config(text=f'{round(level * 100)}%')

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

def mark_changed():
	global playlist_changed
	playlist_changed = True
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

# Open a playlist - replaces the songs that are in the list now
def open_playlist():
	global playlist_file, playlist_changed, current_index
	if not ok_to_discard():
		return
	path = filedialog.askopenfilename(initialdir=playlist_start_folder(), title='Open Playlist', filetypes=(('Playlists', '*.m3u *.m3u8'), ))
	if not path:
		return
	try:
		songs, missing = read_playlist(path)
	except OSError as e:
		messagebox.showerror('Open Playlist', f"Couldn't open the playlist:\n{e}")
		return
	# Empty the current list, then fill it from the file
	stop()
	song_display.delete(0, END)
	song_paths.clear()
	current_index = None
	clear_song_labels()
	for song in songs:
		add_to_playlist(song)
	playlist_file = path
	# Songs that couldn't be found are dropped, so the playlist has changed from what's in the file
	playlist_changed = missing > 0
	update_title()
	if missing:
		status_bar.config(text=f'Opened {display_name(path)} - {missing} song(s) could not be found  ')
	else:
		status_bar.config(text=f'Opened {display_name(path)} - {len(songs)} songs  ')

# Start a new, empty playlist
def new_playlist():
	global playlist_file, playlist_changed
	if not ok_to_discard():
		return
	delete_all_songs()
	playlist_file = None
	playlist_changed = False
	update_title()

# Move the selected song up (-1) or down (+1) the playlist
def move_song(direction):
	global current_index
	selected = song_display.curselection()
	if not selected:
		return
	index = selected[0]
	new_index = index + direction
	if new_index < 0 or new_index >= len(song_paths):
		# Already at the top or bottom
		return
	# Swap the two songs in the list of paths...
	song_paths[index], song_paths[new_index] = song_paths[new_index], song_paths[index]
	# ...and in the listbox
	song_display.delete(index)
	song_display.insert(new_index, display_name(song_paths[new_index]))
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

# Closing the window or pressing Exit - offer to save first
def exit_player():
	if ok_to_discard():
		root.quit()

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

# Title at top of screen
title_label = Label(root, text="MAC's MEGA MIXES", font=("Helvetica", 24), fg="red", bd='1', relief=RAISED)
title_label.pack()

# Create Master Frame
master_frame = Frame(root)
master_frame.pack(pady=20)

# Song display frame + listbox frame
frame_song_display = Frame(master_frame)
frame_song_display.grid(row=0, column=0)
listbox_frame = Frame(frame_song_display)
listbox_frame.grid(row=1, column=0)


# Create Player control frame
control_frame = Frame(master_frame, relief=RIDGE)
control_frame.grid(row=1, column=0, columnspan=2, pady=20)

# Create Playlist Display and Scroll Bar all inside frame_song_display
current_song = Label(frame_song_display, text="", bg="black", fg="green", width=31, font=("Helvetica", 22), relief=RAISED)
current_song.grid(row=0, column=0, columnspan=2)
scroll_song_display = Scrollbar(listbox_frame, orient=VERTICAL)
song_display = Listbox(listbox_frame, bg="black", fg="green", width=35, height=11, relief=RAISED, yscrollcommand=scroll_song_display.set, selectbackground="red", selectforeground="black", exportselection=False)
#Configure scrollbar
scroll_song_display.config(command=song_display.yview)
scroll_song_display.pack(side=RIGHT, fill=Y)
song_display.pack()
song_display.bind("<<ListboxSelect>>", song_selected)

# Move Up / Move Down buttons under the playlist
move_frame = Frame(frame_song_display)
move_frame.grid(row=2, column=0, pady=(5, 0))
move_up_button = Button(move_frame, text='Move Up', width=10, command=move_up)
move_up_button.pack(side=LEFT, padx=5)
move_down_button = Button(move_frame, text='Move Down', width=10, command=move_down)
move_down_button.pack(side=LEFT, padx=5)
Tooltip(move_up_button, 'Move the selected song up the playlist')
Tooltip(move_down_button, 'Move the selected song down the playlist')

# Now playing panel - album art with the song info next to it
info_frame = Frame(frame_song_display, bg="black", relief=RAISED, bd=1)
info_frame.grid(row=1, column=1, sticky=N+S, padx=(5, 0))
# Music note picture, shown when a song has no album art (enlarged to fill the art box)
no_art_img = ImageTk.PhotoImage(Image.open(os.path.join(script_dir, 'icons', '1486505261-eighth-eighth-note-multimedia-player-music-note_81397.png')).convert('RGBA').resize((ART_SIZE, ART_SIZE)))
album_art_label = Label(info_frame, image=no_art_img, bg="black", width=ART_SIZE, height=ART_SIZE)
album_art_label.image = no_art_img
album_art_label.grid(row=0, column=0, padx=5, pady=5)
song_info_label = Label(info_frame, text="No Song Selected", bg="black", fg="green", width=25, height=11, justify=LEFT, anchor=W)
song_info_label.grid(row=0, column=1, padx=5, pady=5)

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
	button.grid(row=0, column=column, padx=(25 if column == 7 else 6, 6))
	Tooltip(button, tip)
	made.append(button)
(back_button, back10_button, play_button, pause_button, stop_button,
	forward10_button, forward_button, shuffle_button, repeat_button) = made

# Create Music Position Slider
my_slider = ttk.Scale(master_frame, from_=0, to=100, orient=HORIZONTAL, value=0, command=slide, length=500)
my_slider.grid(row=2, column=0, pady=10)

# Visualiser and volume side by side under the slider
bottom_frame = Frame(master_frame)
bottom_frame.grid(row=3, column=0, pady=(0, 5))

# Music visualiser - bars that bounce along to the song
visualiser = Visualiser(bottom_frame, song_position, width=500, height=150)
visualiser.grid(row=0, column=0)

# Exit button at bottom of the screen
button_quit = Button(root, text="Exit", bg="red", font=("Helvetica", 22), relief=RAISED, command=exit_player)
button_quit.pack(pady=10)

# Create status bar
status_bar = Label(root, text="", bd=1, relief=GROOVE, anchor=E)
status_bar.pack(fill=X, side=BOTTOM, ipady=2)

# Volume Slider
# Volume sits to the right of the visualiser.
# from_=1 to=0 puts loud at the top, so pushing the slider up makes it louder.
volume_frame = LabelFrame(bottom_frame, text="Volume")
volume_frame.grid(row=0, column=1, sticky=N+S, padx=(15, 0))
volume_slider = ttk.Scale(volume_frame, from_=1, to=0, orient=VERTICAL, value=1, command=volume, length=100)
volume_slider.grid(row=0, column=0, rowspan=2, padx=(8, 2), pady=5)
# Loud speaker at the top and quiet speaker at the bottom show which way is which
vol_up_img = button_image('volume_up')
vol_down_img = button_image('volume_down')
vol_up_label = Label(volume_frame, image=vol_up_img)
vol_up_label.grid(row=0, column=1, sticky=N, padx=(2, 8), pady=5)
vol_down_label = Label(volume_frame, image=vol_down_img)
vol_down_label.grid(row=1, column=1, sticky=S, padx=(2, 8), pady=5)
# Current volume as a percentage
volume_level = Label(volume_frame, text='100%')
volume_level.grid(row=2, column=0, columnspan=2, pady=(0, 5))
Tooltip(volume_slider, lambda: f'Volume {volume_level.cget("text")}')

# Keyboard shortcuts and the window's close (X) button
root.bind('<Control-s>', lambda event: save_playlist())
root.bind('<Control-o>', lambda event: open_playlist())
root.protocol('WM_DELETE_WINDOW', exit_player)
update_title()

root.mainloop()

'''Notes

Note added to check
'''
