import sys, tkinter as tk
sys.path.insert(0, 'src')
from original_data import OriginalData
from pc_game import NativeGame

root = tk.Tk()
app = NativeGame(root, OriginalData('original-1.20.4'))
seen = []
for step in range(4000):
    root.update()
    if app.battle:
        if app.battle.result:
            app.finish_battle()
        else:
            avail = app.battle.available_skills(app.battle.player_active)
            usable = [i for i, e in enumerate(avail, 1) if e['usable']]
            app.battle.choose_skill(usable[0] if usable else 0)
            app.battle_ui._after_action()
            if app.battle.result:
                app.finish_battle()
        continue
    if app.ui_open:
        app.close_ui()
        continue
    if app.display_request:
        if app.display_request.kind in ('talk', 'aside', 'airtalk', 'button', 'tapscreen'):
            seen.append((app.state.map_id, app.state.main_task, app.state.main_state,
                         app.dialogue))
            app.interact()
        else:
            app.interact()
        continue
    if app.runtime.running:
        app.drive()
        continue
    if app.state.map_id == 101 and app.state.main_task == 2:
        app.state.main_state = 4
        app.request_map(10104)
        continue
    if app.state.map_id == 5801:
        npcs = (580104, 580101) if app.state.main_task == 3 and app.state.main_state == 3 else (580101, 580104)
        for npc in npcs:
            if app.runtime.notify('talk', npcid=npc):
                break
        if app.runtime.running:
            continue
    break
print('steps', step, 'events', app.state.events, 'main', app.state.main_task, app.state.main_state)
print('maps seen', [s for s in seen if s[0] in (7401, 7228, 5807, 101, 5801)][-8:])
print('pets', [(p.species, p.level) for p in app.state.pets])
app.make_frame().convert('RGB').save('outputs/verification/host-prologue-current.png')
root.destroy()