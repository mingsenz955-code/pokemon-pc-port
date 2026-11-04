"""Recovery regression: fainted-party challenge and real map NPC clicks.

The old all-fainted guard raised PendingMechanic, became runtime_error and
locked every movement/NPC click. This check drives the original fight request
and then performs a real click on map 101's NPC.
"""
from __future__ import annotations

import os
import sys
import tempfile
import tkinter as tk
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from pc_game import NativeGame
from game_state import GameState


def run():
    with tempfile.TemporaryDirectory() as saves:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = saves
        root = tk.Tk()
        root.withdraw()
        try:
            app = NativeGame(root, OriginalData(ROOT/'original-1.20.4'))
            app.state = GameState(app.data.tables, seed=71)
            app.state.add_preset(1)
            app.runtime.state = app.state
            app.close_transient_ui()
            app.wait_until = 0
            app.camera_action = None
            app.story_motion.actions = []
            app.npc_motion.motion.actions = []

            # Original fight request with every party member fainted.
            for pet in app.state.pets:
                pet.hp = 0
            app.runtime.file = 'pEventRecovery.json'
            app.runtime.sequence = [
                {'id': 1, 'type': 'fight', 'parameters': {'npcid': 105021}}]
            app.runtime.index = 0
            app.runtime.active_trigger = None
            app.runtime.pending = None
            app.display_request = None
            app.pending_wait = None
            app.runtime_error = ''
            app.drive()
            root.update()
            assert not app.runtime.running, 'fainted challenge left the event locked'
            assert app.runtime.pending is None
            assert app.battle is None, 'fainted party must not start a fake battle'
            assert app.runtime_error == '', app.runtime_error
            assert '全灭' in app.event_issue
            assert any(row.get('aborted') == 'all-pets-fainted'
                       for row in app.state.audit), app.state.audit[-3:]

            # A real NPC click on the original map must still open its talk event.
            app.load_map(101, 23*64+32, 31*64+32)
            app.runtime.file, app.runtime.sequence = '', []
            app.runtime.pending, app.display_request = None, None
            app.pending_wait, app.runtime_error = None, ''
            root.update()
            actor = next(a for a in app.actors()
                         if a[0] == '10104' and str(a[1]) != '30001')
            camx, camy = app.camera_origin()
            sprite = app.scene_sprite(actor[1], app.actor_animation(actor[0], actor[1]))
            anchor = sprite.info.get('origin', (sprite.width/2, sprite.height))
            sx = (actor[2]-anchor[0])*app.SCALE-camx+sprite.width*app.SCALE/2
            sy = (actor[3]-anchor[1])*app.SCALE-camy+sprite.height*app.SCALE/2
            app.on_click(SimpleNamespace(x=sx, y=sy))
            for _ in range(40):
                app.guide.step(.1)
                root.update()
                if app.runtime.running or app.display_request:
                    break
            assert app.runtime.file == 'pEventTalk10104.json', app.runtime.file
            assert app.display_request and app.display_request.kind == 'talk'
            assert app.dialogue and '卡姆' in app.dialogue

            # Advancing the talk must not raise "No original event request".
            app.interact()
            root.update()
            assert app.runtime_error == '', app.runtime_error
        finally:
            root.destroy()
    print('Story recovery checks passed')


if __name__ == '__main__':
    run()