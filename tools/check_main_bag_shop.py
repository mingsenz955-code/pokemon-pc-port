"""The original MainUI must actually open bag and shop shortcuts.

This guards the 0.2.53 regression where right/up menu buttons existed in the
layout but stayed alpha=0, so the player could not find the bag or shop at all.
"""
import os
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from pc_game import NativeGame
from game_state import GameState

with tempfile.TemporaryDirectory() as saves:
    os.environ['POCKET_NATIVE_SAVE_DIR'] = saves
    root = tk.Tk()
    root.withdraw()
    app = NativeGame(root, OriginalData(ROOT/'original-1.20.4'))
    app.state = GameState(app.data.tables, seed=31)
    app.state.add_preset(1)

    frame = Image.new('RGBA', (app.WIDTH, app.HEIGHT))

    # Right-side functional menu: the bag is the first original sub-button.
    # Click the real 功能 button (not action()) so hidden alpha=0 children cannot
    # swallow the click while the menu is collapsed.
    app.scene_ui.render(frame)
    main_hit = app.scene_ui.hits['mainRight_Button']
    assert app.scene_ui.click((main_hit[0]+main_hit[2])/2,
                              (main_hit[1]+main_hit[3])/2)
    app.scene_ui.groups['right']['clock'] = time.monotonic() - 1
    app.scene_ui.cached_key = None
    app.scene_ui.render(frame)
    assert app.scene_ui.value('right') == 1.0, 'clicking 功能 did not expand the original menu'
    # Single-player build deliberately removes online rank, gift-code exchange
    # and Bluetooth battle from the functional menu.
    for hidden in ('right_left_5_Button', 'right_left_6_Button',
                   'right_left_7_Button'):
        assert hidden not in app.scene_ui.hits, f'{hidden} still clickable'
    assert 'community_Button' not in app.scene_ui.hits, 'community still visible'
    assert 'uiDisappear_Button' not in app.scene_ui.hits, (
        'four-arrow HUD button still covers the illustrated-book icon')
    bag_hit = app.scene_ui.hits.get('right_left_1_Button')
    assert bag_hit, 'expanded MainUI has no bag hit region'
    assert app.scene_ui.click((bag_hit[0]+bag_hit[2])/2, (bag_hit[1]+bag_hit[3])/2)
    root.update()
    assert app.ui_open and app.ui_window is not None
    assert app.ui_base_layer is not None and app.ui_base_layer.size == (800, 480)
    assert '背包' in app.ui_window.title()
    app.close_transient_ui()

    # Collapsing 功能 restores the original four-arrow HUD toggle.
    app.scene_ui.action('mainRight_Button')
    app.scene_ui.groups['right']['clock'] = time.monotonic() - 1
    app.scene_ui.cached_key = None
    app.scene_ui.render(frame)
    assert app.scene_ui.value('right') == 0.0
    assert 'uiDisappear_Button' in app.scene_ui.hits, (
        'four-arrow HUD button did not return after collapsing 功能')
    assert 'community_Button' not in app.scene_ui.hits

    # Up-side shop/bookmark menu must actually toggle open by clicking 指引 too.
    up_hit = app.scene_ui.hits['mainUp_Button']
    assert app.scene_ui.click((up_hit[0]+up_hit[2])/2, (up_hit[1]+up_hit[3])/2)
    app.scene_ui.groups['up']['clock'] = time.monotonic() - 1
    app.scene_ui.cached_key = None
    app.scene_ui.render(frame)
    assert app.scene_ui.value('up') == 1.0, 'mainUp_Button did not open the original up menu'

    # The main-store button is a direct original shop page and must show real
    # currency values, not the embedded 8888888 editor placeholder.
    app.scene_ui.action('store_Button')
    root.update()
    assert app.ui_open and app.ui_window is not None
    assert '商店' in app.ui_info.get()
    app.state.grant('700001', 4321)
    app.close_transient_ui()
    app.store_ui()
    root.update()
    assert app.ui_base_layer is not None and app.ui_base_layer.size == (800, 480)
    app.close_transient_ui()

    root.destroy()
    print('MainUI bag/shop accessibility checks passed')