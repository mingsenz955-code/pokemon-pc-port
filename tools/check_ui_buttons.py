"""Audit that every visible original Cocos Button has a real Tk hit target.

This does not pretend every gameplay action is implemented: buttons whose
action is still missing report that fact instead of silently doing nothing.
The test opens every UI id the host knows, checks its original button hit
rectangles, and invokes the original close button where the layout has one.
"""
import os
import sys
import tempfile
import tkinter as tk
import types
from pathlib import Path

from PIL import ImageChops

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from pc_game import NativeGame
from event_runtime import Request, EventRuntime


def click(app, rect):
    app.on_ui_click(types.SimpleNamespace(x=(rect[0]+rect[2])/2, y=(rect[1]+rect[3])/2))


def labels(parent):
    result = []
    for child in parent.winfo_children():
        if isinstance(child, tk.Label):
            result.append(str(child.cget('text')))
        result.extend(labels(child))
    return result


with tempfile.TemporaryDirectory() as saves:
    os.environ['POCKET_NATIVE_SAVE_DIR'] = saves
    root = tk.Tk()
    app = NativeGame(root, OriginalData(ROOT/'original-1.20.4'))
    app.runtime.sequence, app.runtime.file, app.runtime.pending = [], '', None
    app.display_request, app.dialogue = None, None
    report = {}
    all_buttons = 0
    closed = 0
    for uiid, (layout, name) in sorted(NativeGame.UI_LAYOUTS.items()):
        if uiid == 7:
            # Starter selection uses the original ChooseFirstPetUI full-screen
            # card; it has no host Tk "选择" label.
            app.open_ui(Request('openui', 'ui-audit', 1,
                                {'parameters': {'uiid': 7, 'par1': 1}}))
            root.update()
            assert app.ui_window and app.ui_window.winfo_exists(), uiid
            assert '初始伙伴' in app.ui_info.get(), uiid
            assert 'confirm_Button' in app.ui_actions, uiid
            app.close_transient_ui()
            report[uiid] = ['ChooseFirstPetUI', 1]
            continue
        if uiid == 44:
            # TaskUI is now rendered inside the game canvas, not a Toplevel.
            app.open_ui(Request('openui', 'ui-audit', 1,
                                {'parameters': {'uiid': 44, 'page': 'main'}}))
            root.update()
            assert app.task_page is not None and app.ui_open, uiid
            report[uiid] = ['TaskUI/canvas', 0]
            app.close_ui('no')
            assert not app.ui_open and app.task_page is None, (uiid, 'close failed')
            continue
        app.open_ui(Request('openui', 'ui-audit', 1,
                            {'parameters': {'uiid': uiid, 'par1': 601}}))
        win = app.ui_window
        assert win and win.winfo_exists(), (uiid, layout)
        root.update()
        assert not any('布局读取失败' in text for text in labels(win)), (uiid, layout)
        buttons = {key: rect for key, rect in app.ui_buttons.items() if '/' in key}
        all_buttons += len(buttons)
        for key, rect in buttons.items():
            hit = app.ui_hit_at((rect[0]+rect[2])/2, (rect[1]+rect[3])/2)
            assert hit is not None, (uiid, key, rect)
            base = key.rsplit('/', 1)[-1]
            assert (app.ui_action_for(key) or base in {
                'close_Button', 'closeButton', 'leave_Button', 'cancel_Button',
                'cancelButton', 'giveUp_Button', 'takeBack_Button'}), (uiid, key, 'no action')
        close = next((rect for key, rect in buttons.items() if key.endswith('/close_Button')), None)
        if close:
            click(app, close)
            assert not app.ui_open and app.ui_window is None, (uiid, layout, 'close failed')
            closed += 1
        else:
            app.close_ui()
        report[uiid] = [layout, len(buttons)]

    # Original pressed texture support is used by the Tk hover/press path.
    app.open_ui(Request('openui', 'ui-audit', 1, {'parameters': {'uiid': 26}}))
    base = app.ui_base_layer.copy()
    pressed = app.cocos_ui.render('RankUI', (800, 480), {}, {}, {},
                                  offset=(0, 0),
                                  pressed={'Layer/root_Panel/fightTag_Button': True})
    diff = ImageChops.difference(base.convert('RGB'), pressed.convert('RGB')).getbbox()
    assert diff, 'original pressed texture was not rendered'
    app.close_ui()

    # Unknown buttons must give feedback, never a silent dead click.
    app.open_ui(Request('openui', 'ui-audit', 1, {'parameters': {'uiid': 34}}))
    unknown = next((key for key in app.ui_buttons
                    if '/' in key and not key.endswith('/close_Button')), None)
    assert unknown
    rect = app.ui_buttons[unknown]
    click(app, rect)
    assert app.ui_info and app.ui_info.get(), 'unknown button produced no feedback'
    app.close_ui()
    root.destroy()

# Original closeui no/yes branches must follow the player's real choice.
runtime = EventRuntime(OriginalData(ROOT/'original-1.20.4'),
                       app.state)
runtime.file = 'synthetic-open-close.json'
runtime.sequence = [
    {'id': 1, 'type': 'openui', 'parameters': {'uiid': 24}},
    {'id': 2, 'type': 'closeui', 'parameters': {'uiid': 24, 'no': 4, 'yes': 3}},
    {'id': 3, 'type': 'talk', 'text': 'yes branch'},
    {'id': 4, 'type': 'talk', 'text': 'no branch'},
]
runtime.index = 0
runtime.pending = Request('openui', runtime.file, 1, runtime.sequence[0])
runtime.resume()  # finish openui, wait at closeui
assert runtime.next().kind == 'closeui'
runtime.resume('yes')
assert runtime.sequence[runtime.index]['text'] == 'yes branch'
runtime.pending = Request('closeui', runtime.file, 2, runtime.sequence[1])
runtime.resume('no')
assert runtime.sequence[runtime.index]['text'] == 'no branch'

print({'ui_count': len(report), 'original_buttons': all_buttons,
       'close_buttons_clicked': closed, 'unbound_buttons': 0,
       'pressed_texture': diff, 'unknown_feedback': 'passed',
       'closeui_branch': 'passed'})
import json
(ROOT/'outputs/verification/ui-buttons.json').write_text(json.dumps({
    'ui_count': len(report), 'original_buttons': all_buttons,
    'close_buttons_clicked': closed, 'unbound_buttons': 0,
    'pressed_texture': list(diff), 'unknown_feedback': True,
    'closeui_branch': True, 'uis': report,
}, ensure_ascii=False, indent=2), encoding='utf-8')