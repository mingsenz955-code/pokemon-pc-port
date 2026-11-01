import sys, json, random
sys.path.insert(0, 'src')
from original_data import OriginalData
from game_state import GameState
from battle import make_npc_battle, make_wild_battle

data = OriginalData('original-1.20.4')
state = GameState(data.tables, 12345)
print('pets', [(p.species, p.level, p.hp, p.stats(data.tables)) for p in state.pets])
b = make_npc_battle(data.tables, state.pets[:1], 101091, state.rng)
print('enemy', [(u.name, u.pet.level, u.hp, u.stats) for u in b.enemy])
print('player', [(u.name, u.hp, u.energy, u.max_hp) for u in b.player])
for i in range(30):
    if b.result:
        break
    print('--- round', b.round+1)
    b.choose_skill(1)
    for m in b.messages[-8:]:
        print('  ', m)
print('result', b.result, 'round', b.round)
if b.result == 'win':
    print('exp', b.exp_gained, 'drops', b.drops)
    b.apply_rewards(state)
print('after', [(u.name, u.hp, u.pet.hp, u.pet.level, u.pet.exp) for u in b.player])