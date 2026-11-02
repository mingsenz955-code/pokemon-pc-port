"""GetItemUI must use the original reward cards, not a host Tk listbox."""
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

with tempfile.TemporaryDirectory() as saves:
    os.environ['POCKET_NATIVE_SAVE_DIR'] = saves
    root = tk.Tk()
    root.withdraw()
    try:
        app = NativeGame(root, OriginalData(ROOT/'original-1.20.4'))
        app.state = GameState(app.data.tables, seed=51)
        app.state.add_preset(1)
        items = [('220001', 3), ('220007', 1), ('230001', 5), ('100084', 1)]
        app.open_ui(Request('openui', 'get-item', 1, {
            'parameters': {'uiid': 49, 'title': '获得物品', 'items': items}}))
        root.update()
        assert app.ui_open and app.ui_window is not None
        assert app.ui_base_layer is not None and app.ui_base_layer.size == (800, 480)
        assert 'item_ListView' in app.ui_rects
        assert 'get_item_0' in app.ui_hits and 'get_item_1' in app.ui_hits
        assert '获得物品' in app.ui_info.get()
        assert '滚轮翻页（1/2）' in app.ui_info.get()
        # The original cards replace the old dark host Listbox entirely.
        def find_listbox(widget):
            for child in widget.winfo_children():
                if isinstance(child, tk.Listbox):
                    return True
                if find_listbox(child):
                    return True
            return False
        assert not find_listbox(app.ui_window)
        app.ui_actions['confirm_Button']()
        assert not app.ui_open
        print('GetItemUI checks passed')
    finally:
        root.destroy()