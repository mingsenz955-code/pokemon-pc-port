"""Original ShopGoodsUI and GoodsBuyConfirmUI purchase path."""
import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from event_runtime import Request  # noqa: E402
from game_state import GameState  # noqa: E402
from original_data import OriginalData  # noqa: E402
from pc_game import NativeGame  # noqa: E402

saves = tempfile.TemporaryDirectory()
previous = os.environ.get('POCKET_NATIVE_SAVE_DIR')
os.environ['POCKET_NATIVE_SAVE_DIR'] = saves.name
root = tk.Tk()
root.withdraw()
try:
    data = OriginalData(ROOT/'original-1.20.4')
    state = GameState(data.tables, seed=53)
    app = NativeGame(root, data)
    app.state = state
    state.inventory['700001'] = 999999
    key, row = sorted(data.tables['Shop'].items(), key=lambda pair: int(pair[0]))[0]
    app.open_ui(Request('openui', 'shop', 1, {'parameters': {'uiid': 1}}))
    assert app.ui_render_args['name'] == 'ShopUI'
    app.open_goods_detail(1, 'Shop', key, row)
    assert app.ui_render_args['name'] == 'ShopGoodsUI'
    assert 'buy_Button' in app.ui_actions
    rect = app.ui_buttons['buy_Button']
    assert app.ui_hit_at((rect[0]+rect[2])/2, (rect[1]+rect[3])/2)[0] == 'buy_Button'
    app.ui_actions['buy_Button']()
    assert app.ui_render_args['name'] == 'GoodsBuyConfirmUI'
    assert state.shop_purchases.get(f'Shop:{key}', 0) == 0
    app.ui_actions['buy_Button']()
    assert state.shop_purchases.get(f'Shop:{key}', 0) == 1
    assert app.ui_render_args['name'] == 'ShopUI'
    app.close_ui()
    assert not app.ui_open
    print('ShopGoodsUI checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous