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

# Set global filepath to current location - Where Filedialog will start on first run
global filepath
filepath = os.getcwd()

# Add song Function
def add_song(path):
	song = filedialog.askopenfilename(initialdir=(path), title="choose A Song", filetypes=(("mp3 Files", "*mp3"), ("m4a Files", "*.m4a"), ))
	print ('Full Path: ' + song)
	# Determine the filepath for the track
	global filepath
	filepath =song.rsplit('/',1)[0]
	print (filepath)
	song = song.replace(filepath, "")
	song = song.replace(".mp3", "")	
	# Insert song into playlist
	song_display.insert(END, song)
	song_display.select_set(0)
	
#Add multiple songs to playlist
def add_multiple(path):
	songs = filedialog.askopenfilenames(initialdir=(path), title="choose A Song", filetypes=(("mp3 Files", "*mp3"), ("m4a Files", "*.m4a"), ))
	for song in songs :
		# Determine the filepath for the track
		global filepath
		filepath =song.rsplit('/',1)[0]
		# Loop thru song list and replace directory info an MP3
		song = song.replace(filepath, "")
		song = song.replace(".mp3", "")
		# Insert into playlist
		song_display.insert(END, song)
		song_display.select_set(0)
			
# delete a song
def delete_song():
	stop()
	song_display.delete(ANCHOR)
	pygame.mixer.music.stop()	
	
# Delete all songs from playlist
def delete_all_songs():
	stop()
	song_display.delete(0, END)
	pygame.mixer.music.stop()

def play_time():
	# if song is stopped cancels play_time loop
	if stopped:
		return
	current_time = pygame.mixer.music.get_pos() / 1000
	#slider_label.config(text=f'Slider: {int(my_slider.get())} and Song Pos: {int(current_time)}')
	# get song title from song list
	song = song_display.get(ACTIVE)
	song = f'{filepath}{song}.mp3'
	# Load Song with Mutagen
	song_mut = MP3(song)
	
	# Get song Length
	global song_length
	song_length = song_mut.info.length
	
	# Convert to Time Format
	converted_length = time.strftime('%H:%M:%S', time.gmtime(song_length))
	
	# increase current time by 1 second
	current_time +=1
	
	if int(my_slider.get()) == int(song_length):
		# Output time to status bar
		status_bar.config(text=f'Time Elapsed: {converted_length} of {converted_length}  ' )
		shuffle()
		
	elif paused:
		pass 
		 
	elif int(my_slider.get()) == int(current_time): #Slider hasn't been moved
		# Update Slider To Positon
		slider_position = int(song_length)
		my_slider.config(to=slider_position, value=int(current_time))
	else: #Slider has been moved!
		
		# Update Slider To Positon
		slider_position = int(song_length)
		my_slider.config(to=slider_position, value=int(my_slider.get()))
		
		# Convert to time format
		converted_time = time.strftime('%H:%M:%S', time.gmtime(int(my_slider.get())))
		
		# Output time to status bar
		status_bar.config(text=f'Time Elapsed: {converted_time} of {converted_length}  ' )
		
		# Movethis thing along by a second
		next_time = int(my_slider.get()) +1
		my_slider.config(value=next_time)
	
	# Update time 
	status_bar.after(1000, play_time)

# Display current playing song 
def song_playing(playing, filepath):
	#Clear active bar in playlist box
	song_display.selection_clear(0, END)
	# Activate new song bar
	song_display.activate(playing)
	# Set Active bar to Next Song
	song_display.selection_set(playing, last=None)
	song = song_display.get(playing)
	song = f'{filepath}{song}.mp3'	
	audio=eyed3.load(song)
	#print("Title:",audio.tag.title)
	title = audio.tag.title
	current_song.config(text=title)
	
#get the information for the playing song 	
def song_info(track):
	audio=eyed3.load(track)
	#print("Title:",audio.tag.title)
	title = audio.tag.title
	artist = audio.tag.artist
	album = audio.tag.album
	album_track = audio.tag.track_num
	composer = audio.tag.composer
	#album_artist = audio.tag.album_artist
	publisher = audio.tag.publisher
	genre = audio.tag.genre.name
	song_mut = MP3(track)
	song_length = song_mut.info.length
	length = time.strftime('%H:%M:%S', time.gmtime(song_length))
	nl = '\n'
	song_info_label.config(text=f'******* {nl} Title: {title} {nl} Duration: {length} {nl} Artist: {artist} {nl} Album: {album} {nl} Track: {album_track} {nl} Compiser: {composer} {nl} Publisher: {publisher} {nl} Genre; {genre} {nl} *******')	
		
def song_selected(event):
	selected = song_display.curselection()
	#Clear active bar in playlist box
	song_display.selection_clear(0, END)
	# Activate new song bar
	song_display.activate(selected)
	# Set Active bar to Next Song
	song_display.selection_set(selected, last=None)
	song = song_display.get(selected)
	song = f'{filepath}{song}.mp3'
	#song = f'/home/pi/tkinter/MP3_Player/audio/{song}.mp3'
	print (song)
	#Update song info label
	song_info(song)

# play selected song	
def play(path):
	global stopped
	stopped = False
	# Reset Slider and Status bar
	status_bar.config(text='')
	my_slider.config(value=0)
	song = song_display.get(ACTIVE)
	song = f'{path}{song}.mp3'
	audio=eyed3.load(song)
	print("Play:",audio.tag.title)
	pygame.mixer.music.load(song)
	pygame.mixer.music.play(loops=0)
	global filepath
	filepath = path
	#get the current tuple number
	playing = song_display.curselection()
	song_playing(playing, filepath)
	song_info(song)
	play_time()

# Check status of shuffle check button
def shuffle():
	print ('Shuffle function Called')
	if shuf.get() == 1:
		print ('Shuffle')
		# count number of songs in song_display ListBox
		global total_songs
		total_songs = song_display.size()
		print (total_songs)		
		shuffle_song()
	else:
		print ('next Song')
		next_song()

global stopped
stopped = False		
# Stop playing current song	

def stop():
	# Reset Slider and Status bar
	status_bar.config(text='')
	my_slider.config(value=0)
	# Stop Song
	pygame.mixer.music.stop()
	song_display.selection_clear(ACTIVE)
	#Clear the status bar
	status_bar.config(text='STOP')
	# Set Stopped Variable to True
	global stopped
	stopped = True
	song_display.select_set(0)
	
def next_song():
	# Reset Slider and Status bar
	status_bar.config(text='')
	my_slider.config(value=0)
	#get the current tuple number
	next_one = song_display.curselection()
	# Add one to the current song number
	next_one = next_one[0]+1
	# get song title from song list
	song = song_display.get(next_one)
	song = f'{filepath}{song}.mp3'
	pygame.mixer.music.load(song)
	pygame.mixer.music.play(loops=0)	
	song_playing(next_one, filepath)
	song_info(song)
	
# Play previous song in playlist
def previous_song():
	# Reset Slider and Status bar
	status_bar.config(text='')
	my_slider.config(value=0)
	#get the current tuple number
	next_one = song_display.curselection()
	# Add one to the current song number
	next_one = next_one[0]-1
	# get song title from song list
	song = song_display.get(next_one)
	song = f'{filepath}{song}.mp3'
	pygame.mixer.music.load(song)
	pygame.mixer.music.play(loops=0)
	song_playing(next_one, filepath)
	song_info(song)
 
 #play random song in playlist
def shuffle_song(): 
	# Reset Slider and Status bar
	status_bar.config(text='')
	my_slider.config(value=0)
	# Select random song
	global random_song
	random_song = randint(0, total_songs-1)
	print (random_song)
	# get song title from song list
	song = song_display.get(random_song)
	song = f'{filepath}{song}.mp3'
	pygame.mixer.music.load(song)
	pygame.mixer.music.play(loops=0)
	song_playing(random_song, filepath)
	song_info(song)	
 
# Create pause variable
global paused
paused = False

# Pause and unpause song	
def pause(is_paused):
	global paused
	paused = is_paused
	if paused:
		pygame.mixer.music.unpause()
		paused = False
	else:
		pygame.mixer.music.pause()
		paused = True

def slide(x):
	#slider_label.config(text=f'{int(my_slider.get())} of {int(song_length)}')
	song = song_display.get(ACTIVE)
	song = f'{filepath}{song}.mp3'
	pygame.mixer.music.load(song)
	pygame.mixer.music.play(loops=0, start=int(my_slider.get()))
	
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
add_song_menu.add_command(label="Add one Song to playlist", command=lambda: add_song(filepath))
# Add Multiple songs to playlist
add_song_menu.add_command(label="Add multipule Songs to playlist", command=lambda: add_multiple(filepath))
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
song_display = Listbox(listbox_frame, bg="black", fg="green", width=35, height=11, relief=RAISED, yscrollcommand=scroll_song_display.set, selectbackground="red", selectforeground="black")
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
play_button = Button(control_frame, image=play_img, borderwidth=0, command=lambda: play(filepath))
pause_button = Button(control_frame, image=pause_img, borderwidth=0, command=lambda: pause(paused))
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

#slider_label = Label(root, text="0")
#slider_label.pack(pady=10)
#mylabel = Label(root, text=shuf.get())
#mylabel.pack()

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
