import sys, tkinter as tk
sys.path.insert(0, 'src')
from original_data import OriginalData
from pc_game import NativeGame

root = tk.Tk()
app = NativeGame(root, OriginalData('original-1.20.4'))
app.start_battle(7401042)
app.battle_ui.render().convert('RGB').save('outputs/verification/battle-ui-main.png')
app.battle_ui.screen = 'skills'
app.battle_ui.render().convert('RGB').save('outputs/verification/battle-ui-skills.png')
app.battle_ui.screen = 'items'
app.battle_ui.render().convert('RGB').save('outputs/verification/battle-ui-items.png')
app.battle_ui.screen = 'pets'
app.battle_ui.render().convert('RGB').save('outputs/verification/battle-ui-pets.png')
print('battle', [(u.name, u.hp) for u in app.battle.player], [(u.name, u.hp) for u in app.battle.enemy])
root.destroy()