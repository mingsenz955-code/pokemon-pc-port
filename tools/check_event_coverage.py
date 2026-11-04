"""Prove every original plot script/trigger/map has a native dispatcher."""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from event_runtime import EventRuntime  # noqa: E402
from original_data import OriginalData  # noqa: E402

data = OriginalData(ROOT/'original-1.20.4')
known_commands = EventRuntime.PRESENTATION | EventRuntime.STATE_COMMANDS | EventRuntime.INTERACTIVE
known_triggers = {'tomap', 'toarea', 'toexit', 'talk', 'fightover', 'fight'}
command_types = Counter()
trigger_rows = data.event('pEventContents.json')
assert len(trigger_rows) == 461, len(trigger_rows)
assert {row['type'] for row in trigger_rows} <= known_triggers
unknown = []
scripts = 0
for path in (ROOT/'original-1.20.4/assets/PlotEvent').glob('pEvent*.json'):
    if path.name == 'pEventContents.json':
        continue
    scripts += 1
    for step in data.event(path.name):
        command_types[step['type']] += 1
        if step['type'] not in known_commands:
            unknown.append((path.name, step['id'], step['type']))
assert scripts == 1685, scripts
assert not unknown, unknown
maps = 0
for mid in data.tables['VillageMap']:
    data.load_map(mid)
    maps += 1
assert maps == 431, maps
print({'scripts': scripts, 'triggers': len(trigger_rows),
       'trigger_types': sorted(known_triggers), 'command_types': len(command_types),
       'unknown_commands': len(unknown), 'village_maps_loaded': maps})