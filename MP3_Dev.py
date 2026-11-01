from tkinter import *
from PIL import ImageTk,Image
import pygame
from tkinter import filedialog
import time
from mutagen.mp3 import MP3
import tkinter.ttk as ttk
from random import randint
import eyed3
import os

root = Tk()
root.title('My MP3')
root.geometry("600x620")
pygame.mixer.init()

# Folder this script lives in - used to find the icons wherever you run it from
script_dir = os.path.dirname(os.path.abspath(__file__))

# Where the file dialog opens - starts at the current folder,
# then remembers the folder the last songs were added from
last_folder = os.getcwd()

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

# Turn a full path into the name shown in the playlist
def display_name(path):
	return os.path.splitext(os.path.basename(path))[0]

# Add one file to the playlist (used by both add functions)
def add_to_playlist(path):
	global last_folder
	song_paths.append(path)
	song_display.insert(END, display_name(path))
	last_folder = os.path.dirname(path)
	# If nothing is selected yet, select the first song
	if not song_display.curselection():
		song_display.select_set(0)

# Add song Function
def add_song():
	song = filedialog.askopenfilename(initialdir=last_folder, title="Choose A Song", filetypes=(("mp3 Files", "*.mp3"), ))
	# Pressing Cancel returns an empty string
	if song:
		add_to_playlist(song)

#Add multiple songs to playlist
def add_multiple():
	songs = filedialog.askopenfilenames(initialdir=last_folder, title="Choose Songs", filetypes=(("mp3 Files", "*.mp3"), ))
	for song in songs:
		add_to_playlist(song)

# Clear the song name and info panels
def clear_song_labels():
	current_song.config(text="")
	song_info_label.config(text="No Song Selected")

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
	if song_paths:
		highlight(current_index if current_index is not None else min(index, len(song_paths) - 1))

# Delete all songs from playlist
def delete_all_songs():
	global current_index
	stop()
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

#get the information for the selected song
def song_info(track):
	tags = read_tags(track)
	length = time.strftime('%H:%M:%S', time.gmtime(get_length(track)))
	nl = '\n'
	song_info_label.config(text=f'******* {nl} Title: {tags["title"]} {nl} Duration: {length} {nl} Artist: {tags["artist"]} {nl} Album: {tags["album"]} {nl} Track: {tags["track"]} {nl} Composer: {tags["composer"]} {nl} Publisher: {tags["publisher"]} {nl} Genre: {tags["genre"]} {nl} *******')

# Clicking a song in the playlist shows its info
def song_selected(event):
	selected = song_display.curselection()
	# This also fires when the selection is cleared, so check something is selected
	if not selected:
		return
	song_info(song_paths[selected[0]])

# Load and play the song at a position in the playlist - everything that plays a song uses this
def play_song(index):
	global current_index, song_length, stopped, paused, timer_id
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
	repeat_button.config(text=repeat_labels[repeat_mode])

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
	global paused
	if stopped or current_index is None:
		return
	pygame.mixer.music.play(loops=0, start=int(my_slider.get()))
	paused = False

def volume(x):
	pygame.mixer.music.set_volume(volume_slider.get())

# Create Menu Bar and cascades
my_menu = Menu(root)
root.config(menu=my_menu)
#add file menu
file_menu = Menu(my_menu)
my_menu.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Exit...", command=root.quit)
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

# Create Volume Label Frame
volume_frame = LabelFrame(master_frame, text="Volume")
volume_frame.grid(row=0, column=1, padx=0)

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
song_info_label = Label(frame_song_display, text="No Song Selected", bg="black", fg="green", width=25, height=11, relief=RAISED)
song_display.bind("<<ListboxSelect>>", song_selected)
song_info_label.grid(row=1, column=1)

# Images for the control buttons
back_img = PhotoImage(file=os.path.join(script_dir, 'icons', 'back.png'))
forward_img = PhotoImage(file=os.path.join(script_dir, 'icons', 'forward.png'))
play_img = PhotoImage(file=os.path.join(script_dir, 'icons', 'play.png'))
pause_img = PhotoImage(file=os.path.join(script_dir, 'icons', 'pause.png'))
stop_img = PhotoImage(file=os.path.join(script_dir, 'icons', 'stop.png'))

#global shuf to set shuffle status as a int Variable
shuf = IntVar()

# Set buttons
back_button = Button(control_frame, image=back_img, borderwidth=0, command=previous_song)
forward_button = Button(control_frame, image=forward_img, borderwidth=0, command=next_track)
play_button = Button(control_frame, image=play_img, borderwidth=0, command=play)
pause_button = Button(control_frame, image=pause_img, borderwidth=0, command=pause)
stop_button = Button(control_frame, image=stop_img, borderwidth=0, command=stop)
mode_frame = Frame(control_frame)
mode_frame.grid(row=1, column=0, columnspan=5, pady=5)
shuffle_button = Checkbutton(mode_frame, text="Shuffle", variable=shuf)
# width keeps the button the same size whichever label it shows
repeat_button = Button(mode_frame, text=repeat_labels[repeat_mode], width=12, command=toggle_repeat)

back_button.grid(row= 0, column=0, padx=10)
forward_button.grid(row= 0, column=1, padx=10)
play_button.grid(row= 0, column=2, padx=10)
pause_button.grid(row= 0, column=3, padx=10)
stop_button.grid(row= 0, column=4, padx=10)
# Shuffle and Repeat sit on their own row under the controls so everything fits the window
shuffle_button.pack(side=LEFT, padx=10)
repeat_button.pack(side=LEFT, padx=10)

# Create Music Position Slider
my_slider = ttk.Scale(master_frame, from_=0, to=100, orient=HORIZONTAL, value=0, command=slide, length=500)
my_slider.grid(row=2, column=0, pady=10)

# Exit button at bottom of the screen
button_quit = Button(root, text="Exit", bg="red", font=("Helvetica", 22), relief=RAISED, command=root.quit)
button_quit.pack(pady=10)

# Create status bar
status_bar = Label(root, text="", bd=1, relief=GROOVE, anchor=E)
status_bar.pack(fill=X, side=BOTTOM, ipady=2)

# Volume Slider
volume_slider = ttk.Scale(volume_frame, from_=0, to=1, orient=VERTICAL, value=1, command=volume, length=175)
volume_slider.pack(pady=10)

root.mainloop()

'''Notes

Note added to check
'''
