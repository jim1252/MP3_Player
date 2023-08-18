from tkinter import *
from PIL import ImageTk,Image
import pygame


root = Tk()
root.title('Learning Tkinter')
root.geometry("500x500")

pygame.mixer.init()

my_menu = Menu(root)
root.config(menu=my_menu)
file_menu = Menu(my_menu)
my_menu.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Exit...", command=root.quit)


title_label = Label(root, text="Zombie", font=("Helvetica", 24), fg="red")
title_label.pack()

def play():
	pygame.mixer.music.load("./audio/Zombie.mp3")
	pygame.mixer.music.play(loops=0)

def stop():
	pygame.mixer.music.stop()

button_play = Button(root, text="Play Song", font=("Helvetica", 24), command=play)
button_play.pack(pady=20)

button_stop = Button(root, text="Stop", font=("Helvetica", 18), command=stop)
button_stop.pack(pady=20)


button_quit = Button(root, text="Exit Program", command=root.quit)
button_quit.pack(pady=20)

root.mainloop()

'''Notes
Tutorial 86

'''
