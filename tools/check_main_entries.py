"""MainUI convenience entries are reachable and open their original layouts."""
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
    app.runtime.file, app.runtime.sequence, app.runtime.pending = '', [], None
    app.load_map(5801, 19*64+32, 20*64)
    app.make_frame()
    expected = {
        'save_Button': ('save_ui', 'SaveConfirmUI'),
        'store_Button': ('store_ui', 'ShopUI'),
        'rechargeReward_Button': ('recharge_ui', 'RechargeFreeUI'),
        'draw_Button': ('lottery_ui', 'LuckyDrawUI'),
        'right_left_1_Button': ('bag_ui', 'BagUI'),
        'right_left_2_Button': ('pets_ui', 'PetListUI'),
        'right_left_3_Button': ('illustrated_ui', 'IllustratedUI'),
        'right_left_4_Button': ('achievements_ui', 'AchievementUI'),
    }
    for key, (method, layout) in expected.items():
        if not key.startswith('right_left_'):
            assert key in app.scene_ui.hits, key
        if method == 'lottery_ui':
            app.state.functions['8'] = 1
        getattr(app, method)()
        root.update()
        assert app.ui_open, (key, method)
        if method != 'lottery_ui':
            assert app.ui_render_args['name'] == layout, (key, app.ui_render_args)
        else:
            assert app.ui_window.winfo_exists(), key
        app.close_ui()
        root.update()
        assert not app.ui_open, key
    print('MainUI entry checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous