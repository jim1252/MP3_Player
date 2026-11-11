# Tooltips - a little label that pops up when the mouse rests on a widget.
#
#   Tooltip(play_button, 'Play')
#
# The text can also be a function, for buttons whose tip changes (like Shuffle: On / Off):
#
#   Tooltip(shuffle_button, lambda: 'Shuffle is on' if shuffling else 'Shuffle is off')

from tkinter import Toplevel, Label

DELAY = 500   # milliseconds the mouse has to rest before the tip appears


class Tooltip:
	def __init__(self, widget, text):
		self.widget = widget
		self.text = text
		self.tip = None
		self.waiting = None
		widget.bind('<Enter>', self.start_wait, add='+')
		widget.bind('<Leave>', self.hide, add='+')
		# Clicking hides the tip so it isn't in the way
		widget.bind('<ButtonPress>', self.hide, add='+')

	def start_wait(self, event=None):
		self.cancel_wait()
		self.waiting = self.widget.after(DELAY, self.show)

	def cancel_wait(self):
		if self.waiting is not None:
			self.widget.after_cancel(self.waiting)
			self.waiting = None

	def show(self):
		self.waiting = None
		text = self.text() if callable(self.text) else self.text
		# Just under the widget, lined up with its middle
		x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
		y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
		self.tip = Toplevel(self.widget)
		# No title bar or border - just the label
		self.tip.wm_overrideredirect(True)
		label = Label(self.tip, text=text, bg='black', fg='#00e000', relief='solid', bd=1, padx=6, pady=2, font=('Helvetica', 10))
		label.pack()
		self.tip.update_idletasks()
		self.tip.wm_geometry(f'+{x - self.tip.winfo_width() // 2}+{y}')

	def hide(self, event=None):
		self.cancel_wait()
		if self.tip is not None:
			self.tip.destroy()
			self.tip = None
