"""Selected party lead survives save/load and starts the next battle."""
from __future__ import annotations

import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from game_state import GameState
from battle import make_npc_battle


def run():
    data = OriginalData(ROOT/'original-1.20.4')
    state = GameState(data.tables, seed=13)
    state.add_preset(1)
    assert len(state.pets) >= 2
    state.active_pet = 1
    selected_uid = state.pets[1].uid
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)/'slot1.json'
        state.save(path)
        loaded = GameState.load(data.tables, path)
    assert loaded.active_pet == 1
    assert loaded.pets[1].uid == selected_uid
    battle = make_npc_battle(data.tables, loaded.pets, 511051, loaded.rng)
    battle.select_initial_player(loaded.active_pet)
    assert battle.player_index == 1
    assert battle.player_active.pet.uid == selected_uid
    # A dead selected lead falls back to the first living member, without
    # silently reordering persistent party slots.
    loaded.pets[1].hp = 0
    battle = make_npc_battle(data.tables, loaded.pets, 511051, loaded.rng)
    battle.select_initial_player(loaded.active_pet)
    assert battle.player_index == 0
    assert loaded.pets[1].uid == selected_uid
    print('Active pet checks passed')


if __name__ == '__main__':
    run()