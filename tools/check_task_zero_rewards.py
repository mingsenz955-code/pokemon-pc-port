"""BranchTask 2801/6201 have no reward rows and must not invent one."""
from __future__ import annotations

import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from pc_game import NativeGame
from game_state import GameState, numbers
from event_runtime import Request


def run():
    with tempfile.TemporaryDirectory() as saves:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = saves
        root = tk.Tk()
        root.withdraw()
        try:
            app = NativeGame(root, OriginalData(ROOT/'original-1.20.4'))
            app.state = GameState(app.data.tables, seed=2801)
            app.state.add_preset(1)
            app.runtime.state = app.state
            app.state.branch_states.update({'2801': 4, '6201': 4})
            app.close_transient_ui()
            app.open_ui(Request('openui', 'tasks', 1,
                                {'parameters': {'uiid': 44, 'page': 'branch'}}))
            page = app.task_page
            page.select_page('branch')
            for task_id in ('2801', '6201'):
                index = next(i for i, row in enumerate(page.rows)
                             if str(row[0]) == task_id)
                page.selected = index
                row = page.rows[index]
                assert not any(numbers(row[1].get('rewardIds', '0')))
                assert not any(numbers(row[1].get('rewardCounts', '0')))
                info = page.info()
                assert '未配置奖励' in info, info
                page.frame = None
                frame = page.render()
                assert frame is not None
                # No RewardItemUI icon may be fabricated for this row.
                assert not page.hits.get('reward_fake_2801')
            before = dict(app.state.inventory)
            page.selected = next(i for i, row in enumerate(page.rows)
                                 if str(row[0]) == '2801')
            page.receive()
            root.update()
            assert app.state.inventory == before, 'zero-reward task minted an item'
            assert app.state.last_rewards == []
        finally:
            root.destroy()
    print('Zero-reward task checks passed')


if __name__ == '__main__':
    run()