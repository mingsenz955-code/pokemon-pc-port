"""Scale the fixed logical game and its input together, including modal pages."""
from types import SimpleNamespace
from PIL import Image, ImageTk


class GameViewport:
    def __init__(self, app):
        self.app = app
        self.scale = 1.0
        self.offset = (0, 0)
        self.fullscreen = False
        self.window_geometry = None
        app.root.resizable(True, True)
        app.root.minsize(640, 384)
        app.canvas.pack_configure(fill='both', expand=True)
        app.canvas.configure(bg='black')
        app.canvas.bind('<Configure>', self.resize)
        app.root.bind('<F11>', self.toggle)
        app.root.bind('<Alt-Return>', self.toggle)
        app.root.bind('<Escape>', self.escape)

    def toggle(self, event=None):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.window_geometry = self.app.root.geometry()
        self.app.root.attributes('-fullscreen', self.fullscreen)
        if not self.fullscreen and self.window_geometry:
            self.app.root.geometry(self.window_geometry)
        self.app.keys.clear()
        return 'break'

    def escape(self, event):
        if self.fullscreen:
            return self.toggle()
        self.app.key_down(event)
        return 'break'

    def resize(self, event):
        self.scale = min(event.width/self.app.WIDTH, event.height/self.app.HEIGHT)
        self.offset = ((event.width-self.app.WIDTH*self.scale)/2,
                       (event.height-self.app.HEIGHT*self.scale)/2)
        if getattr(self.app, 'frame', None) is not None:
            self.present(self.app.frame)
        for overlay in getattr(self.app, '_game_overlays', []):
            overlay.rescale()

    def event(self, event, callback):
        x = (event.x-self.offset[0])/self.scale
        y = (event.y-self.offset[1])/self.scale
        if 0 <= x < self.app.WIDTH and 0 <= y < self.app.HEIGHT:
            values = vars(event).copy()
            values.update(x=x, y=y)
            return callback(SimpleNamespace(**values))

    def bind(self, sequence, callback):
        self.app.canvas.bind(sequence, lambda event: self.event(event, callback))

    def present(self, frame):
        size = (max(1, round(self.app.WIDTH*self.scale)), max(1, round(self.app.HEIGHT*self.scale)))
        shown = frame if frame.size == size else frame.resize(size, Image.Resampling.BILINEAR)
        self.app.tk_image = ImageTk.PhotoImage(shown)
        if not hasattr(self.app, 'canvas_image'):
            self.app.canvas_image = self.app.canvas.create_image(*self.offset, anchor='nw', image=self.app.tk_image)
        else:
            self.app.canvas.itemconfigure(self.app.canvas_image, image=self.app.tk_image)
            self.app.canvas.coords(self.app.canvas_image, *self.offset)
