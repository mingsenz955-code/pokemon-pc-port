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
        self.rescale()

    def rescale(self):
        scale = getattr(getattr(self.app, 'viewport', None), 'scale', 1)
        self.place_configure(width=round(800*scale), height=round(480*scale))
        for child in self.winfo_children():
            if isinstance(child, GameArtLabel) and hasattr(child, 'logical_frame'):
                child.show_frame(child.logical_frame)

    def escape(self, event=None):
        self._close()
        return 'break'

    def destroy(self):
        if getattr(self, '_destroyed', False):
            return
        self._destroyed = True
        if self in getattr(self.app, '_game_overlays', []):
            self.app._game_overlays.remove(self)
        super().destroy()

    def geometry(self, value):
        # Legacy debug selectors can request a size, but stay inside the game.
        # Position-only geometry ("+20+20") is accepted for old test helpers;
        # this child overlay remains centered in the game canvas.
        head = str(value).split('+')[0]
        if 'x' not in head:
            return
        width, height = map(int, head.split('x'))
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
        self.rescale()


class GameArtLabel(tk.Label):
    """Show transparent original panels over the current scene, not black."""
    def __init__(self, parent, **options):
        app = parent.app
        scene = app.make_frame().convert('RGBA')
        # The modal animation pauses map redraws. Publish the clean scene
        # once first, so the previous dialogue/battle cannot remain around it.
        app.frame = scene
        if hasattr(app, 'viewport'):
            app.viewport.present(scene)
        else:
            app.tk_image = ImageTk.PhotoImage(scene, master=app.root)
            if hasattr(app, 'canvas_image'):
                app.canvas.itemconfigure(app.canvas_image, image=app.tk_image)
            else:
                app.canvas_image = app.canvas.create_image(0, 0, anchor='nw', image=app.tk_image)
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
                self.logical_frame = frame
                options['image'] = self.scaled_photo(frame)
        return super().configure(cnf, **options)

    def set_layer(self, layer):
        frame = self.backdrop.copy()
        frame.alpha_composite(layer)
        painter = getattr(self.master.app, 'paint_purchase_notice', None)
        if painter:
            painter(frame)
        self.show_frame(frame)

    def scaled_photo(self, frame):
        from PIL import Image
        self.logical_frame = frame
        scale = getattr(getattr(self.master.app, 'viewport', None), 'scale', 1)
        frame = frame.convert('RGB')
        if scale != 1:
            frame = frame.resize((max(1, round(frame.width*scale)), max(1, round(frame.height*scale))), Image.Resampling.BILINEAR)
        old = getattr(self, 'composited_image', None)
        if old is not None and old.width() == frame.width and old.height() == frame.height:
            old.paste(frame)
        else:
            self.composited_image = ImageTk.PhotoImage(frame, master=self.master.app.root)
        return self.composited_image

    def show_frame(self, frame):
        super().configure(image=self.scaled_photo(frame))

    def bind(self, sequence=None, func=None, add=None):
        if func and sequence and any(name in sequence for name in ('Button', 'Motion', 'MouseWheel')):
            def logical(event):
                from types import SimpleNamespace
                scale = getattr(getattr(self.master.app, 'viewport', None), 'scale', 1)
                values = vars(event).copy()
                values.update(x=event.x/scale, y=event.y/scale)
                return func(SimpleNamespace(**values))
            return super().bind(sequence, logical, add)
        return super().bind(sequence, func, add)
