"""Serial hidden-Tk render/upload costs; includes cold frames and complex pets."""
import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time
import tkinter as tk

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, default=ROOT/'src')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source.resolve()))
from original_data import OriginalData
from pc_game import NativeGame
from battle import Battle
from battle_ui import BattleUI


def summary(values):
    ordered = sorted(values)
    return {'median_ms': round(statistics.median(values), 3),
            'p95_ms': round(ordered[int(.95*(len(values)-1))], 3), 'max_ms': round(max(values), 3)}


with tempfile.TemporaryDirectory(prefix='pocket-late-timing-') as save:
    os.environ['POCKET_NATIVE_SAVE_DIR'] = save
    root = tk.Tk()
    root.withdraw()
    data = OriginalData(ROOT/'original-1.20.4')
    app = NativeGame(root, data)
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    app.screen_black = False
    app.main_ui_visible = True
    app.state.initialize(1)
    app.state.add_preset(201)
    app.state.main_task, app.state.main_state = 155, 5
    app.runtime.file, app.runtime.pending = '', None
    app.story_motion.actions = []
    app.display_request, app.dialogue = None, None
    app.camera_action = None
    result = {'context': 'serial hidden Tk; render and upload time, not monitor FPS', 'scenes': {}}
    try:
        for mid in (7401, 109, 203, 305, 503, 806):
            start = time.perf_counter()
            app.load_map(mid)
            load_ms = (time.perf_counter()-start)*1000
            values = []
            for i in range(180):
                app.scene_animation_time = i/60
                start = time.perf_counter()
                app.viewport.present(app.make_frame())
                values.append((time.perf_counter()-start)*1000)
            result['scenes'][str(mid)] = {'load_ms': round(load_ms, 3),
                'first_frame_ms': round(values[0], 3), 'all': summary(values), 'warm': summary(values[60:])}
        app.load_map(102)
        app.state.pets = [app.state.add_generated_pet('100138', 80)]
        app.battle = Battle(data.tables, app.state.pets, [{'species': '101148', 'level': 80}], app.state.rng, kind='wild')
        app.battle_ui = BattleUI(app, app.battle)
        values = []
        for _ in range(240):
            app.battle_ui.advance(seconds=1/60)
            start = time.perf_counter()
            app.viewport.present(app.make_frame())
            values.append((time.perf_counter()-start)*1000)
        result['complex_pet_battle'] = {'first_frame_ms': round(values[0], 3),
            'all': summary(values), 'warm': summary(values[160:])}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        for job in root.tk.call('after', 'info'):
            root.after_cancel(job)
        root.destroy()
