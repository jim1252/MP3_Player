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
root.geometry("600x580")
pygame.mixer.init()

# Folder the file dialog opens in. Starts as the current folder, then
# remembers the last folder you added songs from.
filepath = os.getcwd()

# Full path of every song in the playlist, in the same order as the playlist box.
# (Bug 3 fix: each song remembers its own folder, so you can mix folders.)
playlist_paths = []

# Position in the playlist of the song that is loaded (None = nothing loaded)
current_index = None

# Length of the loaded song in seconds
song_length = 0

# ID of the 1-second play_time timer, so it can be cancelled.
# (Bug 1 fix: only ever one timer running, so the slider can't speed up.)
timer_id = None

stopped = True
paused = False


# ---------- Helpers ----------

# "/home/pi/Music/Zombie.mp3" -> "Zombie"
def song_name(path):
	return os.path.splitext(os.path.basename(path))[0]

# Read the ID3 tags for a song.
# (Bug 5 fix: files with no tag, or missing fields, no longer crash.)
def read_tags(path):
	tags = {'title': None, 'artist': None, 'album': None, 'track': None,
		'composer': None, 'publisher': None, 'genre': None}
	try:
		audio = eyed3.load(path)
	except Exception as e:
		print('Could not read tags:', e)
		audio = None
	if audio is not None and audio.tag is not None:
		tag = audio.tag
		tags['title'] = tag.title
		tags['artist'] = tag.artist
		tags['album'] = tag.album
		if tag.track_num is not None and tag.track_num[0] is not None:
			tags['track'] = tag.track_num[0]
		tags['composer'] = tag.composer
		tags['publisher'] = tag.publisher
		if tag.genre is not None:
			tags['genre'] = tag.genre.name
	# No title in the tag? Use the file name instead
	if not tags['title']:
		tags['title'] = song_name(path)
	return tags

# Get the length of a song in seconds (0 if it can't be read)
def get_length(path):
	try:
		return MP3(path).info.length
	except Exception as e:
		print('Could not read length:', e)
		return 0

# Highlight a song in the playlist box
def highlight(index):
	song_display.selection_clear(0, END)
	song_display.activate(index)
	song_display.selection_set(index)
	song_display.see(index)

# Start (or restart) the 1-second timer - cancels any timer already running
def start_timer():
	global timer_id
	stop_timer()
	timer_id = root.after(1000, play_time)

def stop_timer():
	global timer_id
	if timer_id is not None:
		root.after_cancel(timer_id)
		timer_id = None


# ---------- Adding / removing songs ----------

def add_to_playlist(path):
	playlist_paths.append(path)
	song_display.insert(END, song_name(path))
	# Highlight the first song if nothing is highlighted yet
	if not song_display.curselection():
		highlight(0)

# Add song Function
# (Bug 4 fix: .m4a removed - pygame can't play them - and the filter now has its dot.)
def add_song():
	global filepath
	song = filedialog.askopenfilename(initialdir=filepath, title="Choose A Song", filetypes=(("mp3 Files", "*.mp3"), ))
	if not song:	# Cancel was pressed
		return
	print ('Full Path: ' + song)
	filepath = os.path.dirname(song)
	add_to_playlist(song)

#Add multiple songs to playlist
def add_multiple():
	global filepath
	songs = filedialog.askopenfilenames(initialdir=filepath, title="Choose Songs", filetypes=(("mp3 Files", "*.mp3"), ))
	for song in songs:
		filepath = os.path.dirname(song)
		add_to_playlist(song)

# delete a song
def delete_song():
	selected = song_display.curselection()
	if not selected:
		return
	index = selected[0]
	stop()
	song_display.delete(index)
	del playlist_paths[index]
	current_song.config(text="")
	song_info_label.config(text="No Song Selected")
	if playlist_paths:
		highlight(0)

# Delete all songs from playlist
def delete_all_songs():
	stop()
	song_display.delete(0, END)
	playlist_paths.clear()
	current_song.config(text="")
	song_info_label.config(text="No Song Selected")


# ---------- Playing ----------

# Load and play the song at a position in the playlist.
# Play, Next, Back, Shuffle and the end of a song all come through here.
def play_index(index, start=0):
	global current_index, song_length, stopped, paused
	if index < 0 or index >= len(playlist_paths):
		return
	path = playlist_paths[index]
	try:
		pygame.mixer.music.load(path)
		pygame.mixer.music.play(loops=0, start=start)
	except pygame.error as e:
		print('Could not play', path, e)
		status_bar.config(text=f'Could not play {song_name(path)}  ')
		return
	current_index = index
	stopped = False
	paused = False
	song_length = get_length(path)
	converted_length = time.strftime('%H:%M:%S', time.gmtime(song_length))
	my_slider.config(to=int(song_length), value=start)
	status_bar.config(text=f'Time Elapsed: 00:00:00 of {converted_length}  ')
	highlight(index)
	tags = read_tags(path)
	print("Play:", tags['title'])
	current_song.config(text=tags['title'])
	show_song_info(path, tags)
	start_timer()

# Called once a second while a song is playing to move the slider along
def play_time():
	global timer_id
	timer_id = None
	# if song is stopped cancels play_time loop
	if stopped:
		return
	converted_length = time.strftime('%H:%M:%S', time.gmtime(song_length))

	if paused:
		pass
	elif int(my_slider.get()) >= int(song_length):
		# End of song - play the next one (or a random one if Shuffle is ticked)
		status_bar.config(text=f'Time Elapsed: {converted_length} of {converted_length}  ')
		shuffle()
		return	# play_index starts a fresh timer for the new song
	else:
		# Move the slider on by a second and show the time
		next_time = int(my_slider.get()) + 1
		my_slider.config(value=next_time)
		converted_time = time.strftime('%H:%M:%S', time.gmtime(next_time))
		status_bar.config(text=f'Time Elapsed: {converted_time} of {converted_length}  ')

	# Check again in a second
	start_timer()

# Show the info panel for a song
def show_song_info(path, tags):
	length = time.strftime('%H:%M:%S', time.gmtime(get_length(path)))
	nl = '\n'
	song_info_label.config(text=f'******* {nl} Title: {tags["title"]} {nl} Duration: {length} {nl} Artist: {tags["artist"]} {nl} Album: {tags["album"]} {nl} Track: {tags["track"]} {nl} Composer: {tags["composer"]} {nl} Publisher: {tags["publisher"]} {nl} Genre: {tags["genre"]} {nl} *******')

# Clicking a song in the playlist shows its info (press Play to play it)
def song_selected(event):
	selected = song_display.curselection()
	if not selected:
		return
	path = playlist_paths[selected[0]]
	show_song_info(path, read_tags(path))

# play selected song
def play():
	if not playlist_paths:
		status_bar.config(text='Playlist is empty - add some songs  ')
		return
	selected = song_display.curselection()
	if selected:
		play_index(selected[0])
	elif current_index is not None:
		play_index(current_index)
	else:
		play_index(0)

# Check status of shuffle check button
def shuffle():
	if shuf.get() == 1:
		shuffle_song()
	else:
		next_song()

# Stop playing current song
def stop():
	global stopped, paused, current_index
	stop_timer()
	pygame.mixer.music.stop()
	stopped = True
	paused = False
	current_index = None
	# Reset Slider and Status bar
	my_slider.config(value=0)
	status_bar.config(text='STOP  ')
	# Go back to the top of the playlist
	if playlist_paths:
		highlight(0)

# Play next song in playlist
# (Bug 2 fix: after the last song, stop instead of crashing.)
def next_song():
	if current_index is None:
		next_one = 0
	else:
		next_one = current_index + 1
	if next_one >= len(playlist_paths):
		stop()
		status_bar.config(text='End of playlist  ')
		return
	play_index(next_one)

# Play previous song in playlist
# (Bug 2 fix: on the first song, Back restarts it instead of misbehaving.)
def previous_song():
	if not playlist_paths:
		return
	if current_index is None or current_index == 0:
		play_index(0)
	else:
		play_index(current_index - 1)

#play random song in playlist
def shuffle_song():
	total_songs = len(playlist_paths)
	if total_songs == 0:
		return
	random_song = randint(0, total_songs - 1)
	# Try not to play the same song twice in a row
	if total_songs > 1:
		while random_song == current_index:
			random_song = randint(0, total_songs - 1)
	play_index(random_song)

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

# Slider moved - jump to that point in the song
# (Bug 6 fix: if paused, it jumps but stays paused.)
def slide(x):
	if stopped or current_index is None:
		return
	position = int(my_slider.get())
	pygame.mixer.music.load(playlist_paths[current_index])
	pygame.mixer.music.play(loops=0, start=position)
	if paused:
		pygame.mixer.music.pause()
	converted_time = time.strftime('%H:%M:%S', time.gmtime(position))
	converted_length = time.strftime('%H:%M:%S', time.gmtime(song_length))
	status_bar.config(text=f'Time Elapsed: {converted_time} of {converted_length}  ')

def volume(x):
	pygame.mixer.music.set_volume(volume_slider.get())
	# Get current volume
	#current_volume = pygame.mixer.music.get_volume()
	#slider_label.config(text=current_volume * 100)

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
back_img = PhotoImage(file='icons/back.png')
forward_img = PhotoImage(file='icons/forward.png')
play_img = PhotoImage(file='icons/play.png')
pause_img = PhotoImage(file='icons/pause.png')
stop_img = PhotoImage(file='icons/stop.png')

#global shuf to set shuffle status as a int Variable
shuf = IntVar()

# Set buttons
back_button = Button(control_frame, image=back_img, borderwidth=0, command=previous_song)
forward_button = Button(control_frame, image=forward_img, borderwidth=0, command=shuffle)
play_button = Button(control_frame, image=play_img, borderwidth=0, command=play)
pause_button = Button(control_frame, image=pause_img, borderwidth=0, command=pause)
stop_button = Button(control_frame, image=stop_img, borderwidth=0, command=stop)
shuffle_button = Checkbutton(control_frame, text="Shuffle", variable=shuf)

back_button.grid(row= 0, column=0, padx=10)
forward_button.grid(row= 0, column=1, padx=10)
play_button.grid(row= 0, column=2, padx=10)
pause_button.grid(row= 0, column=3, padx=10)
stop_button.grid(row= 0, column=4, padx=10)
shuffle_button.grid(row=0, column=5, padx=10)

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
