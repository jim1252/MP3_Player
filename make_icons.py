# Draws the player's control button pictures so they all match.
#
# Run it once to (re)make the pictures in the icons folder:
#     python make_icons.py
# Change the colours or sizes below and run it again to restyle every button at once.

import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageOps

# ---------------- Style ----------------
SIZE = 56              # size of each button picture in pixels (the Play button is a bit bigger)
PLAY_SIZE = 66
FACE = '#111111'       # inside of the button
ON = '#00e000'         # green - matches the playlist text
OFF = '#707070'        # grey - used for Shuffle/Repeat when they're switched off
SCALE = 4              # drawn 4 times bigger then shrunk, which gives smooth edges

script_dir = os.path.dirname(os.path.abspath(__file__))
icon_dir = os.path.join(script_dir, 'icons')


def font(size):
	for name in ('DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'arialbd.ttf'):
		try:
			return ImageFont.truetype(name, size)
		except OSError:
			pass
	return ImageFont.load_default(size)


# A blank round button. Everything is drawn on a 100 x 100 grid (times SCALE) so the shapes
# below don't need to know the final size.
def blank(colour):
	img = Image.new('RGBA', (100 * SCALE, 100 * SCALE), (0, 0, 0, 0))
	d = ImageDraw.Draw(img)
	d.ellipse(p(3, 3, 97, 97), fill=FACE, outline=colour, width=4 * SCALE)
	return img, d


# Scale grid points up to the drawing size
def p(*values):
	return [v * SCALE for v in values]


def triangle(d, colour, x, y, w, h, pointing='right'):
	if pointing == 'right':
		pts = [(x, y), (x + w, y + h / 2), (x, y + h)]
	else:
		pts = [(x + w, y), (x, y + h / 2), (x + w, y + h)]
	d.polygon([(a * SCALE, b * SCALE) for a, b in pts], fill=colour)


# Arrowhead at (x, y) pointing in direction (dx, dy)
def arrowhead(d, colour, x, y, dx, dy, length=13, width=14):
	n = math.hypot(dx, dy)
	dx, dy = dx / n, dy / n
	tip = (x + dx * length * 0.6, y + dy * length * 0.6)
	back = (x - dx * length * 0.4, y - dy * length * 0.4)
	left = (back[0] - dy * width / 2, back[1] + dx * width / 2)
	right = (back[0] + dy * width / 2, back[1] - dx * width / 2)
	d.polygon([(a * SCALE, b * SCALE) for a, b in (tip, left, right)], fill=colour)


def line(d, colour, points, width=6):
	d.line([(a * SCALE, b * SCALE) for a, b in points], fill=colour, width=width * SCALE, joint='curve')


def save(img, name, size=SIZE):
	img = img.resize((size, size), Image.LANCZOS)
	img.save(os.path.join(icon_dir, name))
	print('made', name)


# ---------------- The buttons ----------------

def play():
	img, d = blank(ON)
	triangle(d, ON, 38, 28, 36, 44)
	save(img, 'btn_play.png', PLAY_SIZE)


def pause():
	img, d = blank(ON)
	d.rounded_rectangle(p(33, 29, 45, 71), radius=2 * SCALE, fill=ON)
	d.rounded_rectangle(p(55, 29, 67, 71), radius=2 * SCALE, fill=ON)
	save(img, 'btn_pause.png')


def stop():
	img, d = blank(ON)
	d.rounded_rectangle(p(31, 31, 69, 69), radius=3 * SCALE, fill=ON)
	save(img, 'btn_stop.png')


# Previous song: bar then two triangles pointing left. Next song is the mirror image.
def previous_next():
	img, d = blank(ON)
	d.rectangle(p(25, 32, 31, 68), fill=ON)
	triangle(d, ON, 31, 32, 22, 36, 'left')
	triangle(d, ON, 51, 32, 22, 36, 'left')
	save(img, 'btn_previous.png')
	save(ImageOps.mirror(img), 'btn_next.png')


# Back/forward 10 seconds: a round arrow with "10" in the middle
def skip10():
	img, d = blank(ON)
	cx, cy, r = 50, 52, 27
	# The arc goes most of the way round, leaving a gap at the top for the arrowhead
	d.arc(p(cx - r, cy - r, cx + r, cy + r), start=-65, end=245, fill=ON, width=5 * SCALE)
	# Arrowhead at the top-right end, pointing anticlockwise (to the left = going back)
	a = math.radians(-65)
	arrowhead(d, ON, cx + r * math.cos(a), cy + r * math.sin(a), math.sin(a), -math.cos(a))
	forward = ImageOps.mirror(img)
	for picture, name in ((img, 'btn_back10.png'), (forward, 'btn_forward10.png')):
		# Write "10" after mirroring so the numbers don't come out backwards
		ImageDraw.Draw(picture).text(p(cx, cy + 1), '10', fill=ON, font=font(21 * SCALE), anchor='mm')
		save(picture, name)


# Shuffle: two crossing arrows
def shuffle():
	for colour, name in ((OFF, 'btn_shuffle_off.png'), (ON, 'btn_shuffle_on.png')):
		img, d = blank(colour)
		line(d, colour, [(24, 37), (37, 37), (57, 63), (68, 63)])
		line(d, colour, [(24, 63), (37, 63), (57, 37), (68, 37)])
		arrowhead(d, colour, 72, 37, 1, 0)
		arrowhead(d, colour, 72, 63, 1, 0)
		save(img, name)


# Repeat: a loop of two arrows. Repeat Song has a 1 in the middle.
def repeat():
	for colour, name, one in ((OFF, 'btn_repeat_off.png', False), (ON, 'btn_repeat_all.png', False), (ON, 'btn_repeat_song.png', True)):
		img, d = blank(colour)
		line(d, colour, [(27, 52), (27, 36), (64, 36)])
		arrowhead(d, colour, 70, 36, 1, 0)
		line(d, colour, [(73, 48), (73, 64), (36, 64)])
		arrowhead(d, colour, 30, 64, -1, 0)
		if one:
			d.text(p(50, 51), '1', fill=colour, font=font(20 * SCALE), anchor='mm')
		save(img, name)


# Speakers for the volume control: loud (with sound waves) and quiet
def speakers():
	for name, waves in (('btn_volume_up.png', True), ('btn_volume_down.png', False)):
		img, d = blank(ON)
		d.polygon([(a * SCALE, b * SCALE) for a, b in ((24, 41), (34, 41), (48, 28), (48, 72), (34, 59), (24, 59))], fill=ON)
		if waves:
			d.arc(p(42, 36, 62, 64), start=-50, end=50, fill=ON, width=5 * SCALE)
			d.arc(p(42, 26, 78, 74), start=-50, end=50, fill=ON, width=5 * SCALE)
		else:
			# A small cross for quiet
			line(d, ON, [(57, 42), (73, 58)], width=5)
			line(d, ON, [(73, 42), (57, 58)], width=5)
		save(img, name, 30)


if __name__ == '__main__':
	play()
	pause()
	stop()
	previous_next()
	skip10()
	shuffle()
	repeat()
	speakers()
