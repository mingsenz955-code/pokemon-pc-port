"""Real-click regression for the original pEvent101006 tutorial chain.

Covers the blocked path that previously stopped at ``store_Button``:
store -> free exp stone -> close -> bag -> chooseItem -> use -> pet select.
Uses only the original event steps and Store row 1; never touches the user's
save because every run points POCKET_NATIVE_SAVE_DIR at a temporary folder.
"""
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


def click_ui(app, key):
    target = key if key in app.ui_hits else app._ui_tutorial_target(key)
    if not target:
        raise AssertionError(f'UI tutorial target missing: {key}')
    rect = app.ui_hits[target]
    app.on_ui_click(type('Event', (), {
        'x': (rect[0]+rect[2])/2, 'y': (rect[1]+rect[3])/2})())


def click_scene(app, key):
    rect = app.scene_ui.hits.get(key)
    if not rect:
        raise AssertionError(f'scene button missing: {key}')
    app.on_click(type('Event', (), {
        'x': (rect[0]+rect[2])/2, 'y': (rect[1]+rect[3])/2})())


def wait_for_ui_wait(app, seconds=2.0):
    end = time.monotonic()+seconds
    while app.pending_wait and time.monotonic() < end:
        time.sleep(.03)
        app.root.update()


def run():
    with tempfile.TemporaryDirectory() as saves:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = saves
        root = tk.Tk()
        root.withdraw()
        try:
            app = NativeGame(root, OriginalData(ROOT/'original-1.20.4'))
            app.state = GameState(app.data.tables, seed=101006)
            app.state.add_preset(1)
            app.runtime.state = app.state
            app.state.main_task, app.state.main_state = 7, 4
            app.close_transient_ui()
            app.wait_until = 0
            app.camera_action = None
            app.story_motion.actions = []
            app.npc_motion.motion.actions = []
            app.scene_ui.groups['right'].update(target=0.0, start=0.0,
                                               clock=time.monotonic())
            app.scene_ui.cached_key = None
            app.scene_ui.render(app.make_frame().convert('RGBA'))

            # Start at original step 27 (store_Button) of pEvent101006.
            app.runtime.file = 'pEvent101006.json'
            app.runtime.sequence = app.data.event('pEvent101006.json')
            app.runtime.index = 26
            app.runtime.active_trigger = None
            app.runtime.pending = None
            app.display_request = None
            app.pending_wait = None
            app.runtime_error = ''
            app.main_ui_visible = True
            app.drive()
            root.update()
            assert app.display_request and app.display_request.data['nodekey'] == 'store_Button'

            click_scene(app, 'store_Button')
            root.update()
            assert app.ui_open, 'store did not open'
            wait_for_ui_wait(app)
            root.update()
            assert app.display_request and app.display_request.data['nodekey'] == 'buy_Button_1'

            before = app.state.count('230011')
            assert before == 0
            click_ui(app, 'buy_Button_1')
            root.update()
            assert app.state.count('230011') == 1, 'free tutorial exp stone was not granted'
            # The repeat flag must not mint a second free stone.
            app.ui_actions['buy_Button_1']()
            root.update()
            assert app.state.count('230011') == 1, 'tutorial free stone granted twice'
            assert app.display_request and app.display_request.data['nodekey'] == 'close_Button'

            click_ui(app, 'close_Button')
            root.update()
            assert not app.ui_open
            assert app.display_request and app.display_request.data['nodekey'] == 'mainRight_Button'

            click_scene(app, 'mainRight_Button')
            wait_for_ui_wait(app)
            root.update()
            assert app.display_request and app.display_request.data['nodekey'] == 'right_left_1_Button'

            click_scene(app, 'right_left_1_Button')
            wait_for_ui_wait(app)
            root.update()
            assert app.ui_open
            assert app.display_request and app.display_request.data['nodekey'] == 'chooseItem_230011'

            click_ui(app, 'chooseItem_230011')
            root.update()
            assert app.display_request and app.display_request.data['nodekey'] == 'use_Button'

            level_before = app.state.pets[0].level
            click_ui(app, 'use_Button')
            wait_for_ui_wait(app)
            root.update()
            assert app.display_request and app.display_request.data['nodekey'] == 'petSelectItem_1'

            click_ui(app, 'petSelectItem_1')
            root.update()
            assert app.state.count('230011') == 0, 'exp stone was not consumed'
            assert app.state.pets[0].level == level_before+5, (
                f'expected +5 levels, got {level_before}->{app.state.pets[0].level}')
            assert 7 in app.state.completed_main, 'original submittask 7 did not complete'
            assert app.runtime_error == ''
        finally:
            root.destroy()
    print('Tutorial story checks passed')


if __name__ == '__main__':
    run()