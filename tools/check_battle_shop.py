"""BattleMainUI battleShop_Button and original BattleShopUI purchase."""
import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData  # noqa: E402
from pc_game import NativeGame  # noqa: E402

saves = tempfile.TemporaryDirectory()
previous = os.environ.get('POCKET_NATIVE_SAVE_DIR')
os.environ['POCKET_NATIVE_SAVE_DIR'] = saves.name
root = tk.Tk()
root.withdraw()
try:
    app = NativeGame(root, OriginalData(ROOT/'original-1.20.4'))
    app.runtime.sequence, app.runtime.file, app.runtime.pending = [], '', None
    app.runtime_error, app.dialogue, app.display_request, app.pending_wait = '', None, None, None
    app.state.initialize(2)
    app.state.grant('700001', 100000)
    app.start_battle(1002011)
    ui = app.battle_ui
    ui.render()
    assert 'battleShop_Button' in ui.hits
    rect = ui.hits['battleShop_Button']
    ui.click(round((rect[0]+rect[2])/2), round((rect[1]+rect[3])/2))
    assert ui.shop_window is not None
    rows = sorted(app.data.tables['BattleShop'].items(), key=lambda pair: int(pair[0]))
    goods_id = rows[0][1]['goodsKid']
    before_goods = app.state.count(goods_id)
    before_money = app.state.count('700001')
    ui.shop_box.selection_set(0)
    ui.shop_actions['buy']()
    assert app.state.count(goods_id) > before_goods
    assert app.state.count('700001') < before_money
    ui.shop_actions['close']()
    assert ui.shop_window is None
    print('battle shop checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous