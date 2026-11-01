import sys, tkinter as tk, collections
sys.path.insert(0, 'src')
from original_data import OriginalData
from pc_game import NativeGame

root = tk.Tk()
app = NativeGame(root, OriginalData('original-1.20.4'))
counts = collections.Counter()
for step in range(600):
    root.update()
    tag = ('battle' if app.battle else 'ui' if app.ui_open else
           'display:'+app.display_request.kind if app.display_request else
           'running' if app.runtime.running else 'idle')
    counts[tag] += 1
    if step % 50 == 0:
        print(step, tag, app.state.map_id, app.state.main_task, app.state.main_state,
              app.dialogue, app.runtime.file, app.runtime.index,
              'wait=', bool(app.pending_wait), 'pending=', app.runtime.pending.kind if app.runtime.pending else None,
              'ui=', app.ui_open, 'display=', app.display_request.kind if app.display_request else None)
    if app.battle:
        if app.battle.result or not app.battle.player_active:
            app.finish_battle()
        else:
            avail = app.battle.available_skills(app.battle.player_active)
            usable = [i for i, e in enumerate(avail, 1) if e['usable']]
            app.battle.choose_skill(usable[0] if usable else 0)
            app.battle_ui._after_action()
        continue
    if app.ui_open:
        app.close_ui(); continue
    if app.display_request:
        app.interact(); continue
    if app.runtime.running:
        app.drive(); continue
    if app.state.map_id == 5807:
        if app.runtime.notify('toarea', area=580701):
            continue
    if app.state.map_id == 101 and app.state.main_task == 1:
        if app.runtime.notify('toarea', area=10101):
            continue
    if app.state.map_id == 101 and app.state.main_task == 2:
        app.request_map('580101')
        continue
    if app.state.map_id == 5801 and app.state.main_task >= 4:
        app.request_map('10104')
        continue
    if app.state.map_id == 101 and app.state.main_task == 5:
        app.request_map('580201')
        continue
    if app.state.map_id == 5802 and app.state.main_task == 5:
        if app.runtime.notify('toarea', area=580201):
            continue
    if app.state.map_id == 101 and app.state.main_task == 4:
        app.request_map('580701')
        continue
    if app.state.map_id == 5807 and app.state.main_task == 4:
        app.advance_main_condition('talk', 580701)
        if app.runtime.notify('talk', npcid=580701):
            continue
    if app.state.map_id == 5801:
        npcs = (580104, 580101) if app.state.main_task == 3 and not app.state.pets else (580101, 580104)
        for npc in npcs:
            app.advance_main_condition('talk', npc)
            if app.runtime.notify('talk', npcid=npc):
                break
        if app.runtime.running:
            continue
    break
print(counts)
print('ERR', app.runtime_error, 'ISSUE', app.event_issue, 'MAP', app.map_id, app.map.info['name'], app.x, app.y)
print(app.state.events, app.state.main_task, app.state.main_state, app.state.pets)
root.destroy()