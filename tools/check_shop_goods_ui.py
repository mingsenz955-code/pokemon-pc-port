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
    assert app.ui_base_layer.size == (800, 480)
    assert 'shop_goods_0' in app.ui_actions
    assert 'goods_ListView' in app.ui_rects
    assert hasattr(app, 'shop_scroll')
    first_keys = set(app.ui_actions)
    app.shop_scroll(1)
    assert 'shop_goods_0' not in app.ui_actions
    assert set(app.ui_actions) != first_keys
    app.shop_scroll(-1)
    assert 'shop_goods_0' in app.ui_actions
    app.ui_actions['shop_goods_0']()
    assert app.ui_render_args['name'] == 'ShopUI'
    buy_key = next(k for k in app.ui_buttons if k.startswith('shop_goods_0/') and k.endswith('/buy_Button'))
    rect = app.ui_buttons[buy_key]
    assert app.ui_hit_at((rect[0]+rect[2])/2, (rect[1]+rect[3])/2)[0] == buy_key
    app.ui_action_for(buy_key)()
    assert app.ui_render_args['name'] == 'BuyConfirmUI'
    assert state.shop_purchases.get(f'Shop:{key}', 0) == 0
    app.ui_actions['right_Button']()
    app.ui_actions['right_Button']()
    app.ui_actions['confirm_Button']()
    assert state.shop_purchases.get(f'Shop:{key}', 0) == 3
    assert state.activities['shop_spent']['700001'] >= int(row['price'])*3
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