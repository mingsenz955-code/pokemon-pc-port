"""Child widgets for game panels: never create another operating-system window."""
import tkinter as tk
from PIL import ImageTk


class GameOverlay(tk.Frame):
    def __init__(self, app):
        super().__init__(app.canvas, bg='#202b30', width=800, height=480)
        self.app = app
        self.pack_propagate(False)
        self.place(relx=.5, rely=.5, anchor='center', width=800, height=480)
        self.lift()
        self._close = self.destroy
        app._game_overlays = getattr(app, '_game_overlays', [])+[self]
        self.bind('<Escape>', self.escape)
        app.keys.clear()

    def escape(self, event=None):
        self._close()
        return 'break'

    def destroy(self):
        if self in getattr(self.app, '_game_overlays', []):
            self.app._game_overlays.remove(self)
        super().destroy()

    def geometry(self, value):
        # Legacy debug selectors can request a size, but stay inside the game.
        width, height = map(int, value.split('+')[0].split('x'))
        self.place_configure(width=min(800, width), height=min(480, height))

    def title(self, value=None):
        return value

    def transient(self, *args):
        pass

    def resizable(self, *args):
        pass

    def protocol(self, name, callback):
        if name == 'WM_DELETE_WINDOW':
            self._close = callback

    def withdraw(self):
        self.place_forget()

    def deiconify(self):
        self.place(relx=.5, rely=.5, anchor='center', width=800, height=480)


class GameArtLabel(tk.Label):
    """Show transparent original panels over the current scene, not black."""
    def __init__(self, parent, **options):
        app = parent.app
        scene = app.make_frame().convert('RGBA')
        self.backdrop = scene.crop(((scene.width-800)//2, (scene.height-480)//2,
                                    (scene.width+800)//2, (scene.height+480)//2))
        super().__init__(parent, **options)
        if options.get('image') is not None:
            self.configure(image=options['image'])

    def configure(self, cnf=None, **options):
        photo = options.get('image')
        if photo is not None and hasattr(self, 'backdrop'):
            layer = ImageTk.getimage(photo)
            if layer.size == self.backdrop.size:
                frame = self.backdrop.copy()
                frame.alpha_composite(layer)
                self.composited_image = ImageTk.PhotoImage(frame)
                options['image'] = self.composited_image
        return super().configure(cnf, **options)

    def set_layer(self, layer):
        frame = self.backdrop.copy()
        frame.alpha_composite(layer)
        self.composited_image = ImageTk.PhotoImage(frame)
        super().configure(image=self.composited_image)
