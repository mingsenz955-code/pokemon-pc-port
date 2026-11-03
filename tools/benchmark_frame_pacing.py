"""Comparable hidden-Tk frame costs and live timer cadence with isolated saves."""
import argparse
import json
import os
import statistics
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, default=ROOT/'src')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source.resolve()))
from original_data import OriginalData
from pc_game import NativeGame
from game_state import GameState
from event_runtime import EventRuntime, Request
from battle import make_wild_battle
from battle_ui import BattleUI


def summary(values):
    values = sorted(values)
    return {'median_ms': round(statistics.median(values), 3),
            'p95_ms': round(values[int((len(values)-1)*.95)], 3),
            'worst_ms': round(max(values), 3)}


with tempfile.TemporaryDirectory(prefix='pocket-frame-benchmark-') as folder:
    os.environ['POCKET_NATIVE_SAVE_DIR'] = folder
    root = tk.Tk()
    root.withdraw()
    app = NativeGame(root, OriginalData(ROOT/'original-1.20.4'))
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    app.state = GameState(app.data.tables, seed=1070)
    app.state.initialize(1)
    app.state.add_preset(1)
    app.state.main_task, app.state.main_state = 155, 5
    app.runtime = EventRuntime(app.data, app.state)
    app.display_request = app.dialogue = app.pending_wait = None
    app.runtime_error = ''
    app.camera_action = None
    app.story_motion.actions = []
    app.state.inventory.update({'700001': 100000, '700002': 1000})
    results = {'context': 'hidden Tk; render + upload costs; not monitor FPS'}
    def sample(name, operation, count=180):
        values = []
        for i in range(count):
            app.scene_animation_time += 1/60
            started = time.perf_counter()
            operation()
            values.append((time.perf_counter()-started)*1000)
        results[name] = {'cold_first_ms': round(values[0], 3), 'all': summary(values),
                         'warm': summary(values[count//3:])}
    try:
        for mid, name in [(101, 'town'), (5805, 'bank')]:
            app.load_map(mid)
            def draw():
                app.frame = app.make_frame()
                app.viewport.present(app.frame)
            sample(name+'_render_upload', draw)
            app.player_walking = True
            def walk():
                app.x += .75
                draw()
            sample(name+'_camera_motion', walk)
        app.load_map(102)
        app.battle = make_wild_battle(app.data.tables, app.state.pets, 607001, app.state.rng)
        app.battle_ui = BattleUI(app, app.battle)
        def battle_frame():
            app.battle_ui.advance(seconds=1/60)
            app.viewport.present(app.make_frame())
        sample('battle_idle', battle_frame)
        app.battle = app.battle_ui = None
        app.open_ui(Request('openui', 'benchmark', 0, {'parameters': {'uiid': 47}}))
        page = app.original_page
        def panel():
            page.effect_start -= 1/60
            page.animate()
        sample('pet_panel', panel)
        app.close_ui()
        app.load_map(101)
        for job in root.tk.call('after', 'info'):
            root.after_cancel(job)
        original_present = app.viewport.present
        timestamps = []
        def observe(frame):
            original_present(frame)
            timestamps.append(time.perf_counter())
            if len(timestamps) >= 180:
                root.after(0, root.quit)
        app.viewport.present = observe
        app.last_time = app._play_clock = time.monotonic()
        app.tick()
        root.after(15000, root.quit)
        root.mainloop()
        intervals = [(b-a)*1000 for a, b in zip(timestamps, timestamps[1:])][20:]
        results['live_tick_intervals'] = summary(intervals)
        results['live_tick_intervals']['average_hz'] = round(1000/statistics.mean(intervals), 2)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(json.dumps(results, indent=2))
    finally:
        for job in root.tk.call('after', 'info'):
            root.after_cancel(job)
        root.destroy()
