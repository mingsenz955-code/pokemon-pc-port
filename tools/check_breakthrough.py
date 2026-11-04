"""Original PetTuPoUI action: real cost, +1 tier, insufficient/max failures."""
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
from game_state import GameState
from event_runtime import Request


def run():
    with tempfile.TemporaryDirectory() as saves:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = saves
        root = tk.Tk()
        root.withdraw()
        try:
            app = NativeGame(root, OriginalData(ROOT/'original-1.20.4'))
            app.state = GameState(app.data.tables, seed=23)
            app.state.add_preset(1)
            app.runtime.state = app.state
            pet = app.state.pets[0]
            pet.breakthrough = 0
            row = app.data.tables['PetTuPo']['1']
            app.state.inventory[str(row['costMoneyType'])] = int(row['costMoneyCount'])
            app.state.inventory[str(row['stuffId'])] = int(row['stuffCount'])
            app.close_transient_ui()
            app.open_ui(Request('openui', 'tupo', 1, {'parameters': {'uiid': 23}}))
            assert app.ui_open and app.original_page.specs[0][0] == 'PetTuPoUI'
            assert 'Layer/root_Panel/tuPo_Button' in app.ui_hits and 'tu_po_pet_0' in app.ui_hits
            rect = app.ui_hits['Layer/root_Panel/tuPo_Button']
            before_money = app.state.count(row['costMoneyType'])
            before_stuff = app.state.count(row['stuffId'])
            app.on_ui_click(type('Event', (), {
                'x': (rect[0]+rect[2])/2, 'y': (rect[1]+rect[3])/2})())
            assert pet.breakthrough == 1, pet.breakthrough
            assert app.state.count(row['costMoneyType']) == before_money-int(row['costMoneyCount'])
            assert app.state.count(row['stuffId']) == before_stuff-int(row['stuffCount'])
            assert '突破成功' in app.ui_info.get(), app.ui_info.get()

            # Reopen a fresh page for the insufficient-material branch.
            app.state.inventory[str(row['costMoneyType'])] = 0
            app.state.inventory[str(row['stuffId'])] = 0
            pet.breakthrough = 0
            app.close_ui('no')
            app.open_ui(Request('openui', 'tupo', 1, {'parameters': {'uiid': 23}}))
            snapshot = app.state.payload()
            app.ui_actions['tuPo_Button']()
            assert pet.breakthrough == 0
            assert app.state.payload() == snapshot
            assert ('不足' in app.ui_info.get() or '缺少' in app.ui_info.get()), app.ui_info.get()

            # Max tier must fail without consuming anything.
            pet.breakthrough = max(int(k) for k in app.data.tables['PetTuPo'])
            app.ui_info.set('')
            snapshot = app.state.payload()
            app.ui_actions['tuPo_Button']()
            assert pet.breakthrough == max(int(k) for k in app.data.tables['PetTuPo'])
            assert app.state.payload() == snapshot
            assert '上限' in app.ui_info.get(), app.ui_info.get()
            app.ui_actions['close_Button']()
        finally:
            root.destroy()
    print('Breakthrough checks passed')


if __name__ == '__main__':
    run()