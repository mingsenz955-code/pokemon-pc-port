"""Original Sound/name2 resolution and nonblocking Windows music/effect channels."""
from pathlib import Path
from queue import Queue
from threading import Thread
import os


class GameAudio:
    def __init__(self, data, send=None):
        self.data = data
        self.music_enabled = self.effects_enabled = True
        self.current = None
        self.requested = None
        self.errors = []
        self._resolved = {}
        self.queue = Queue()
        self.send = send
        if send is None and os.name == 'nt':
            import ctypes
            self.send = ctypes.windll.winmm.mciSendStringW
        self.worker = Thread(target=self._run, daemon=True, name='original-audio')
        self.worker.start()

    def resolve(self, value):
        row = value if isinstance(value, dict) else self.data.tables['Sound'].get(str(value), {})
        names = [row.get('name2'), row.get('name')]
        if not row and isinstance(value, str):
            names.append(value)
        key = tuple(names)
        if key in self._resolved:
            return self._resolved[key]
        for name in names:
            if name and Path(name).name == name:
                path = self.data.assets/'Audio'/name
                if path.is_file():
                    self._resolved[key] = path.resolve()
                    return self._resolved[key]
        self._resolved[key] = None
        return None

    def music(self, value, loop=True):
        self.requested = value
        self.loop = loop
        path = self.resolve(value) if self.music_enabled else None
        if path == self.current:
            return
        self.current = path
        self.queue.put(('music', path, loop))

    def effect(self, value):
        if self.effects_enabled:
            path = self.resolve(value)
            if path:
                self.queue.put(('effect', path, False))

    play = effect

    def effect2(self, value):
        """Second simultaneous effect channel (enemy and player entry cries)."""
        if self.effects_enabled:
            path = self.resolve(value)
            if path:
                self.queue.put(('effect2', path, False))

    def pause_music(self):
        self.queue.put(('pause', None, False))

    def resume_music(self):
        if self.music_enabled:
            self.queue.put(('resume', None, False))

    def set_enabled(self, kind, enabled):
        if kind == 'music':
            self.music_enabled = bool(enabled)
            self.music(self.requested, getattr(self, 'loop', True))
        else:
            self.effects_enabled = bool(enabled)
            if not enabled:
                self.queue.put(('effect', None, False))
                self.queue.put(('effect2', None, False))

    def _run(self):
        while True:
            item = self.queue.get()
            try:
                if item is None:
                    for alias in ('pocket_bgm', 'pocket_effect', 'pocket_effect2'):
                        self._command('close '+alias)
                    return
                kind, path, loop = item
                if kind in ('pause', 'resume'):
                    if self.current is not None:
                        self._command(kind+' pocket_bgm')
                    continue
                alias = {'music': 'pocket_bgm', 'effect': 'pocket_effect',
                         'effect2': 'pocket_effect2'}.get(kind, 'pocket_effect')
                self._command('close '+alias)
                if path and not self._command(f'open "{path}" type mpegvideo alias {alias}'):
                    self._command(f'play {alias}'+(' repeat' if loop else ' from 0'))
            finally:
                self.queue.task_done()

    def _command(self, text):
        if self.send is None:
            return 0
        try:
            result = self.send(text, None, 0, None)
            if result and not text.startswith('close '):
                self.errors.append((text, result))
            return result
        except Exception as error:
            self.errors.append((text, str(error)))
            return 1

    def close(self):
        self.queue.put(None)
