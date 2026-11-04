"""RouletteUI: real original page, start/refresh clicks, cost and result."""
from __future__ import annotations

import os
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from pc_game import NativeGame
from game_state import GameState
from event_runtime import Request


def click(app, key):
    target = key if key in app.ui_hits else next(
        (name for name in app.ui_hits if name.rsplit('/', 1)[-1] == key), None)
    if not target:
        raise AssertionError(f'missing hit {key}: {list(app.ui_hits)[:20]}')
    rect = app.ui_hits[target]
    app.on_ui_click(type('Event', (), {
        'x': (rect[0]+rect[2])/2, 'y': (rect[1]+rect[3])/2})())


def pump(root, seconds=1.0):
    end = time.monotonic()+seconds
    while time.monotonic() < end:
        time.sleep(.04)
        root.update()


def run():
    with tempfile.TemporaryDirectory() as saves:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = saves
        root = tk.Tk()
        root.withdraw()
        try:
            app = NativeGame(root, OriginalData(ROOT/'original-1.20.4'))
            app.state = GameState(app.data.tables, seed=29)
            app.state.add_preset(1)
            app.runtime.state = app.state
            app.state.inventory['220009'] = 3
            app.state.inventory['700002'] = 3
            app.close_transient_ui()
            app.open_ui(Request('openui', 'roulette', 1, {'parameters': {'uiid': 29}}))
            assert app.ui_open and app.original_page.specs[0][0] == 'RouletteUI'
            assert 'Layer/root_Panel/start_Button' in app.ui_hits
            assert 'Layer/root_Panel/refresh_Button' in app.ui_hits
            assert 'roulette_slot_0' in app.ui_hits
            assert len(app.state.activities.get('roulette_board', [])) == 12

            tickets = app.state.count('220009')
            click(app, 'Layer/root_Panel/start_Button')
            assert app.state.count('220009') == tickets-1
            pump(root, 1.0)
            # Six highlight steps plus result/reward overlay.
            assert app.original_page is None or app.original_page.specs[0][0] in (
                'GetItemUI', 'RouletteUI')
            if app.ui_actions.get('confirm_Button'):
                app.ui_actions['confirm_Button']()
                pump(root, .1)
            # Return to the roulette page after the real reward overlay.
            assert app.original_page.specs[0][0] == 'RouletteUI'

            badges = app.state.count('700002')
            click(app, 'Layer/root_Panel/refresh_Button')
            assert app.state.count('700002') == badges-1
            assert app.original_page.specs[0][0] == 'RouletteUI'

            app.state.inventory['220009'] = 0
            snapshot = app.state.payload()
            click(app, 'Layer/root_Panel/start_Button')
            assert app.state.payload() == snapshot
            assert app.original_page.specs[0][0] == 'RouletteUI'
            assert '轮盘券' in app.ui_info.get(), app.ui_info.get()
            click(app, 'close_Button')
            assert not app.ui_open
        finally:
            for job in root.tk.call('after', 'info'):
                root.after_cancel(job)
            root.destroy()
    print('Roulette UI checks passed')


if __name__ == '__main__':
    run()