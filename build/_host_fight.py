import sys, tkinter as tk
sys.path.insert(0, 'src')
from original_data import OriginalData
from pc_game import NativeGame

root = tk.Tk()
app = NativeGame(root, OriginalData('original-1.20.4'))

# trainer fight, normal attack until it ends
app.start_battle(1002001)
for turn in range(30):
    if app.battle.result:
        break
    app.battle.choose_skill(0)
    app.battle_ui._after_action()
print('trainer', app.battle.result, app.battle.round, app.battle.messages[-3:])
app.battle_ui.render().convert('RGB').save('outputs/verification/host-fight-result.png')
app.finish_battle()
print('after finish', app.state.main_task, app.state.events.get('1002001'))

# wild capture through the host
app.state.inventory['220004'] = 5
app.start_battle('607001', 'wild')
for turn in range(30):
    if app.battle.result:
        break
    app.battle.choose_item('220004')
    app.battle_ui._after_action()
print('wild', app.battle.result, app.battle.round, app.battle.messages[-3:])
app.battle_ui.render().convert('RGB').save('outputs/verification/host-catch-result.png')
app.finish_battle()
print('party', [(p.species, p.level, p.hp) for p in app.state.pets])
root.destroy()