"""Battle event markers used by one-shot/status achievements."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from battle import make_wild_battle  # noqa: E402
from game_state import GameState  # noqa: E402
from original_data import OriginalData  # noqa: E402

data = OriginalData(ROOT/'original-1.20.4')
state = GameState(data.tables, seed=71)
enemy_id = next(iter(data.tables['VillageEnemy']))
battle = make_wild_battle(data.tables, state.pets, enemy_id, state.rng)
battle._deal(battle.player_active, battle.enemy_active, 999999, 'power')
assert any(e.get('type') == 'oneshot' for e in battle.events)
assert not battle.enemy_active.alive
print('Battle achievement event checks passed')