"""Meaningful migration checks: all maps parse; original event is replayed; unsupported battle stops."""
import json
import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'src'))
from original_data import OriginalData
from pc_preview import Preview


root_dir = Path(__file__).resolve().parent.parent
data = OriginalData(root_dir/'original-1.20.4')
assert len(data.tables['Pet']) == 315
assert len(data.tables['VillageMap']) == 431
for mid in data.tables['VillageMap']:
    scene = data.load_map(mid)
    for name, values, _ in scene.layers:
        assert len(values) == scene.width*scene.height, (mid, name)

root = tk.Tk()
root.withdraw()
app = Preview(root, data)
assert app.dialogue == '皮诺:你总算来了！'
app.next_step()
assert app.dialogue == '尼尔:抱歉！抱歉！睡过头了！'
app.next_step()
assert '朗基罗博士' in app.dialogue
app.next_step()
assert app.dialogue is None and app.task_state['1'] == 'submitted-in-preview'
app.steps, app.step_index = [{'id': 1, 'type': 'fight', 'parameters': {'npcid': 1}}], 0
app.next_step()
assert 'fight' in app.event_issue and '未跳过或伪造' in app.event_issue

app.load_map(102)
assert app.map.info['name'] == '镇东树林'
app.save_path = root_dir/'outputs/verification/test-position.json'
app.save()
saved = (app.map_id, app.x, app.y)
app.load_map(101)
app.restore()
assert saved == (app.map_id, app.x, app.y)
app.save_path.unlink()
app.play_event('pEvent101001.json')
app.frame = app.make_frame()
assert app.frame.size == (1024, 576)
root.destroy()
result = {'map_configurations_parsed': 431, 'original_prologue_replay': 'passed',
          'unimplemented_battle_stops_without_inventing_result': 'passed',
          'preview_position_round_trip': 'passed', 'frame_generation': 'passed',
          'complete_gameplay_validation': 'not implemented'}
(root_dir/'outputs/verification/checks.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
