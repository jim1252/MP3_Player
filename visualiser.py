# Music visualiser - bouncing bars that follow the song that's playing.
#
# How it works:
#  1. When a song starts, a background thread decodes the whole MP3 into raw sound samples
#     (pygame can do this with mixer.Sound) and works out how loud each band of frequencies
#     is, 30 times a second, from start to finish. Bass is on the left, treble on the right.
#  2. 30 times a second the bars are redrawn, using the levels for the exact point the song
#     has reached. That's why they match the music, even after you drag the slider.
#
# Needs numpy:  pip install numpy

import threading
from tkinter import Canvas
import numpy as np
import pygame
import pygame.sndarray

# ---------------- Settings you can tweak ----------------
FPS = 30               # how many times a second the bars are worked out and redrawn
BANDS = 20             # number of bars
SEGMENTS = 12          # number of lights in each bar
LOWEST_HZ = 50         # frequency of the left-hand bar
HIGHEST_HZ = 14000     # frequency of the right-hand bar
FALL_SPEED = 0.06      # how quickly bars drop (bigger = faster)
PEAK_HOLD = 12         # frames the little peak light waits before it starts to fall
LATENCY = 0.05         # seconds - if the bars look slightly early, make this bigger
RANGE_DB = 45          # loudness range shown, from an empty bar to a full one

# Colours of each light from the bottom up: lit and unlit
GREEN, YELLOW, RED = '#00e000', '#f0e000', '#ff2020'
DIM_GREEN, DIM_YELLOW, DIM_RED = '#003000', '#303000', '#300808'
PEAK_COLOUR = 'white'

FFT_SIZE = 2048        # number of samples looked at for each frame


# Work out the level (0 to 1) of every band for every frame of a song.
# Returns a numpy array with one row per frame and one column per band.
def analyse(path, still_wanted):
	rate = pygame.mixer.get_init()[0]
	sound = pygame.mixer.Sound(path)
	samples = pygame.sndarray.array(sound)
	del sound
	# Mix stereo down to one channel
	if samples.ndim == 2:
		samples = samples.mean(axis=1, dtype=np.float32)
	else:
		samples = samples.astype(np.float32)
	samples /= 32768.0
	# Pad the ends so frames at the very start and end have a full block of samples
	half = FFT_SIZE // 2
	samples = np.pad(samples, (half, half))

	# Sample where each frame starts - one frame every 1/30th of a second
	starts = np.arange(0, len(samples) - FFT_SIZE + 1, rate / FPS).astype(np.int64)

	# Which FFT bins belong to which band - bands are spaced like a piano keyboard
	# (each one a fixed step higher than the last), so bass doesn't get squashed into one bar
	freqs = np.fft.rfftfreq(FFT_SIZE, 1 / rate)
	edges = np.geomspace(LOWEST_HZ, HIGHEST_HZ, BANDS + 1)
	band_map = np.zeros((len(freqs), BANDS), dtype=np.float32)
	for b in range(BANDS):
		in_band = (freqs >= edges[b]) & (freqs < edges[b + 1])
		if not in_band.any():
			# Band narrower than one bin (very low notes) - use the nearest bin
			in_band = np.zeros(len(freqs), dtype=bool)
			in_band[np.argmin(abs(freqs - (edges[b] + edges[b + 1]) / 2))] = True
		band_map[in_band, b] = 1 / in_band.sum()

	window = np.hanning(FFT_SIZE).astype(np.float32)
	offsets = np.arange(FFT_SIZE)
	db = np.zeros((len(starts), BANDS), dtype=np.float32)
	# Do 300 frames at a time so a Raspberry Pi doesn't run out of memory
	for i in range(0, len(starts), 300):
		if not still_wanted():
			return None
		chunk = samples[starts[i:i + 300, None] + offsets] * window
		power = np.abs(np.fft.rfft(chunk, axis=1)) ** 2
		db[i:i + 300] = 10 * np.log10(power @ band_map + 1e-12)

	if len(db) == 0:
		return db
	# Scale each band to the song, so treble bars move as much as bass bars.
	# A band can't be boosted more than 25dB though, or quiet hiss would fill the bar.
	loudest = np.percentile(db, 99, axis=0)
	loudest = np.maximum(loudest, loudest.max() - 25)
	levels = (db - (loudest - RANGE_DB)) / RANGE_DB
	return np.clip(levels, 0, 1)


class Visualiser:
	# parent: the frame to put it in
	# get_time: function giving how far through the song we are in seconds (None when not playing)
	def __init__(self, parent, get_time, width=500, height=110):
		self.get_time = get_time
		self.canvas = Canvas(parent, width=width, height=height, bg='black', highlightthickness=0)
		self.levels = None      # the analysed song
		self.song = None        # path of the song being shown
		self.generation = 0     # goes up each time a new song loads, so old analyses are ignored

		# What's shown now - starts with every bar empty
		self.shown = [0.0] * BANDS
		self.peaks = [0] * BANDS
		self.peak_wait = [0] * BANDS

		# Build every light once, then just change colours - much quicker than redrawing
		gap = 3
		bar_w = (width - gap * (BANDS + 1)) / BANDS
		seg_h = (height - gap * (SEGMENTS + 1)) / SEGMENTS
		self.lights = []
		self.lit_colour = []
		self.dim_colour = []
		self.state = []
		for s in range(SEGMENTS):
			if s < SEGMENTS * 0.6:
				self.lit_colour.append(GREEN); self.dim_colour.append(DIM_GREEN)
			elif s < SEGMENTS * 0.85:
				self.lit_colour.append(YELLOW); self.dim_colour.append(DIM_YELLOW)
			else:
				self.lit_colour.append(RED); self.dim_colour.append(DIM_RED)
		for b in range(BANDS):
			x = gap + b * (bar_w + gap)
			column = []
			for s in range(SEGMENTS):
				# s = 0 is the bottom light
				y = height - gap - (s + 1) * (seg_h + gap) + gap
				column.append(self.canvas.create_rectangle(x, y, x + bar_w, y + seg_h, fill=self.dim_colour[s], width=0))
			self.lights.append(column)
			self.state.append([self.dim_colour[s] for s in range(SEGMENTS)])
		# Message shown while a song is being analysed
		self.message = self.canvas.create_text(width / 2, height / 2, text='', fill='grey70', font=('Helvetica', 12))

		self.tick()

	# Put the visualiser on screen (works like grid() on any widget)
	def grid(self, **options):
		self.canvas.grid(**options)

	# Start analysing a new song in the background
	def load(self, path):
		if path == self.song:
			# Same song again (Repeat, or Back on the first song) - already analysed
			return
		self.song = path
		self.levels = None
		self.generation += 1
		gen = self.generation
		self.canvas.itemconfig(self.message, text='Tuning in...')
		self.canvas.tag_raise(self.message)

		def worker():
			try:
				levels = analyse(path, lambda: self.generation == gen)
			except Exception as e:
				print('Visualiser could not read', path, e)
				levels = None
				if self.generation == gen:
					# Tkinter must only be touched from the main thread, so ask it to do this
					self.canvas.after(0, lambda: self.canvas.itemconfig(self.message, text="Can't show bars for this song"))
				return
			if self.generation == gen and levels is not None:
				self.levels = levels
				self.canvas.after(0, lambda: self.canvas.itemconfig(self.message, text=''))

		# daemon=True means it won't stop the program closing
		threading.Thread(target=worker, daemon=True).start()

	# Runs 30 times a second to move the bars
	def tick(self):
		target = [0.0] * BANDS
		t = self.get_time()
		levels = self.levels
		if t is not None and levels is not None and len(levels):
			frame = int((t - LATENCY) * FPS)
			if 0 <= frame < len(levels):
				target = levels[frame]

		for b in range(BANDS):
			# Jump straight up to a louder level, but fall slowly - that's what makes it bounce
			self.shown[b] = max(float(target[b]), self.shown[b] - FALL_SPEED)
			height = round(self.shown[b] * SEGMENTS)
			# The peak light sits on the highest point for a moment, then drops a light at a time
			if height >= self.peaks[b]:
				self.peaks[b] = height
				self.peak_wait[b] = PEAK_HOLD
			elif self.peak_wait[b] > 0:
				self.peak_wait[b] -= 1
			elif self.peaks[b] > 0:
				self.peaks[b] -= 1
			for s in range(SEGMENTS):
				if s < height:
					colour = self.lit_colour[s]
				elif s == self.peaks[b] - 1 and self.peaks[b] > height:
					colour = PEAK_COLOUR
				else:
					colour = self.dim_colour[s]
				# Only change lights that need it - keeps it light on the Pi's processor
				if self.state[b][s] != colour:
					self.canvas.itemconfig(self.lights[b][s], fill=colour)
					self.state[b][s] = colour

		self.canvas.after(1000 // FPS, self.tick)
