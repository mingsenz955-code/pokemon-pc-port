import sys, json
sys.path.insert(0, 'src')
from original_data import OriginalData
from game_state import GameState
from battle import make_wild_battle

data = OriginalData('original-1.20.4')
state = GameState(data.tables, 777)
# Use a generated low-level pet so capture is meaningful.
pet = state.add_generated_pet('100001', 5)
b = make_wild_battle(data.tables, [pet], '607001', state.rng)
print('wild', [(u.name, u.pet.level, u.hp, u.max_hp) for u in b.enemy])
print('chance full', b.capture_chance('220004'))
b.enemy_active.hp = 1
print('chance 1hp', b.capture_chance('220004'))
b.enemy_active.hp = b.enemy_active.max_hp
for i in range(20):
    if b.result: break
    b.choose_item('220004')
    print('round', b.round, b.messages[-3:])
print('result', b.result, 'caught', b.caught_pet.species if b.caught_pet else None)
if b.result == 'caught':
    b.apply_rewards(state)
    print('party', [(p.species, p.level, p.hp) for p in state.pets])
    print('bank', len(state.bank))