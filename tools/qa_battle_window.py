"""Interactive source QA in a temporary save directory; never touches player saves."""
import os
import argparse
import sys
import tempfile
import tkinter as tk
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from pc_game import NativeGame
from event_runtime import EventRuntime
parser = argparse.ArgumentParser()
parser.add_argument('--shiny', action='store_true')
parser.add_argument('--capture', action='store_true')
args = parser.parse_args()

with tempfile.TemporaryDirectory(prefix='pocket-097-visual-') as folder:
    os.environ['POCKET_NATIVE_SAVE_DIR'] = folder
    root = tk.Tk()
    app = NativeGame(root, OriginalData(ROOT/'x-data'))
    app.opening = app.splash = None
    app.booting = False
    app.runtime = EventRuntime(app.data, app.state)
    app.display_request = app.dialogue = app.pending_wait = None
    app.load_map(102)
    app.runtime.file = None
    app.runtime.sequence = []
    if args.shiny:
        lead = app.state.pets[0]
        linked = app.data.tables['Pet'][lead.species].get('flashPetId')
        if linked in app.data.tables['Pet']:
            lead.species = linked
        lead.quality = 4
    app.start_battle(next(iter(app.data.tables['VillageEnemy'])), 'wild')
    if args.capture:
        app.state.inventory['220006'] = 9
        app.battle.enemy_active.hp = 1
    root.title('口袋妖怪 0.2.100 · 战斗验证（临时存档）')
    root.after(300000, root.destroy)
    try:
        root.mainloop()
    finally:
        app.audio.close()
