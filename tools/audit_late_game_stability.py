"""Bounded native map/pet rendering audit plus original event graph checks.

Workers isolate Tk, save directories and caches. Timing in the concurrent
sweep is diagnostic only; remeasure slow scenes serially before claiming FPS.
"""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
import traceback

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData


def worker(kind, keys):
    data = OriginalData(ROOT/'original-1.20.4')
    rows = []
    with tempfile.TemporaryDirectory(prefix='pocket-late-audit-') as save:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = save
        import tkinter as tk
        from pc_game import NativeGame
        root = tk.Tk()
        root.withdraw()
        app = NativeGame(root, data)
        for job in root.tk.call('after', 'info'):
            root.after_cancel(job)
        app.screen_black = False
        app.main_ui_visible = True
        app.state.initialize(1)
        app.state.add_preset(1)
        app.state.main_task, app.state.main_state = 155, 5
        app.runtime.file, app.runtime.sequence, app.runtime.pending = '', [], None
        app.display_request, app.dialogue, app.pending_wait = None, None, None
        app.story_motion.actions = []
        app.camera_action = None
        try:
            for key in keys:
                row = {'kind': kind, 'id': key}
                try:
                    if kind == 'map':
                        started = time.perf_counter()
                        app.load_map(int(key))
                        row['load_ms'] = round((time.perf_counter()-started)*1000, 2)
                        # Decode every visible actor, including off-screen ones.
                        missing = []
                        for oid, sid, _, _ in app.actors():
                            if app.scene_sprite(sid, app.actor_animation(oid, sid)) is None:
                                missing.append([oid, sid])
                        row['missing_actor_art'] = missing
                        samples = []
                        for i in range(13):
                            app.scene_animation_time = i/30
                            started = time.perf_counter()
                            frame = app.make_frame()
                            app.viewport.present(frame)
                            samples.append((time.perf_counter()-started)*1000)
                        row.update(first_frame_ms=round(samples[0], 2),
                                   warm_median_ms=round(statistics.median(samples[1:]), 2),
                                   warm_max_ms=round(max(samples[1:]), 2))
                        # Exercise patrol waits, destinations and movement callbacks.
                        for _ in range(40):
                            app.npc_motion.advance(.25)
                        app.viewport.present(app.make_frame())
                    else:
                        started = time.perf_counter()
                        setup = data.pet_image(key)
                        row['missing_art'] = setup is None
                        for clip in ('stand', 'attack', 'dead'):
                            data.pet_clip_duration(key, clip)
                            for frame in (0, 7):
                                pose = data.pet_frame(key, clip, frame, True, fps=30, limit=300)
                                if pose is not None:
                                    assert min(pose.size) > 0
                        row['decode_ms'] = round((time.perf_counter()-started)*1000, 2)
                    row['ok'] = True
                except Exception:
                    row['ok'], row['error'] = False, traceback.format_exc()
                rows.append(row)
        finally:
            for job in root.tk.call('after', 'info'):
                root.after_cancel(job)
            root.destroy()
    print(json.dumps(rows, ensure_ascii=False))


def graph_audit(data):
    from event_runtime import EventRuntime
    from game_state import GameState
    state = GameState(data.tables, seed=79)
    runtime = EventRuntime(data, state)
    issues = []
    files = list((data.root/'events').glob('*.json'))
    for path in files:
        if path.name == 'pEventContents.json':
            continue
        try:
            runtime.file = ''
            runtime.start(path.name)
            ids = {int(row['id']) for row in runtime.sequence}
            for row in runtime.sequence:
                kind, parameters = row['type'], row.get('parameters', {})
                if kind not in runtime.PRESENTATION | runtime.STATE_COMMANDS | runtime.INTERACTIVE:
                    issues.append({'file': path.name, 'step': row['id'], 'unknown': kind})
                targets = []
                if kind == 'goto':
                    targets = [r['id'] for r in (parameters if isinstance(parameters, list) else [parameters])]
                elif kind in ('accepttask', 'fightover', 'closeui', 'fight'):
                    targets = [v for k, v in parameters.items() if k in ('yes', 'no', 'win', 'lose')]
                for target in targets:
                    if int(target) not in ids:
                        issues.append({'file': path.name, 'step': row['id'], 'missing_jump': target})
                if kind == 'tomap':
                    target = str(parameters['exit'])
                    mid = next((target[:-n] for n in (2, 1) if target[:-n] in data.tables['VillageMap']), None)
                    world = data.load_map(mid) if mid else None
                    if not world or not any(o['group'] == 'spriteLayer' and not o.get('gid')
                                            and str(o['name']) == target for o in world.objects):
                        issues.append({'file': path.name, 'step': row['id'], 'missing_exit': target})
        except Exception:
            issues.append({'file': path.name, 'error': traceback.format_exc()})
    return {'files': len(files)-1, 'issues': issues}


def run_job(job):
    kind, keys = job
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    process = subprocess.Popen([sys.executable, __file__, '--worker', kind, '--keys', ','.join(keys)],
                               cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               encoding='utf-8', env=env)
    try:
        stdout, stderr = process.communicate(timeout=150)
        if process.returncode:
            raise RuntimeError(stderr[-3000:])
        return json.loads(stdout)
    except Exception as error:
        if process.poll() is None:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
            else:
                process.kill()
        return [{'kind': kind, 'id': key, 'ok': False, 'worker_error': str(error)} for key in keys]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', choices=('map', 'pet'))
    parser.add_argument('--keys')
    parser.add_argument('--section', choices=('all', 'maps', 'pets'), default='all')
    parser.add_argument('--output', type=Path, default=ROOT/'outputs/verification/late-game')
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, args.keys.split(','))
    else:
        data = OriginalData(ROOT/'original-1.20.4')
        args.output.mkdir(parents=True, exist_ok=True)
        graph = graph_audit(data)
        (args.output/'event-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Event files:', graph['files'], 'graph issues:', len(graph['issues']), flush=True)
        jobs = []
        for kind, table, batch in [('map', 'VillageMap', 8), ('pet', 'Pet', 16)]:
            if args.section != 'all' and args.section != kind+'s':
                continue
            keys = sorted(data.tables[table], key=int)
            jobs += [(kind, keys[i:i+batch]) for i in range(0, len(keys), batch)]
        rows = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            for future in concurrent.futures.as_completed([pool.submit(run_job, job) for job in jobs]):
                batch = future.result()
                rows.extend(batch)
                print('Checked:', len(rows), 'failures:', sum(not row['ok'] for row in rows), flush=True)
                (args.output/'render-audit.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Complete:', len(rows), 'failures:', sum(not row['ok'] for row in rows), flush=True)
