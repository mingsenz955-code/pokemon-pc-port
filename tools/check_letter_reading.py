"""Dad's letter is re-read from original story data, without replaying that story."""
import copy
import os
from pathlib import Path
import re
import sys
import tempfile
import tkinter as tk
import unittest
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'src'))
from original_data import OriginalData
from pc_game import NativeGame
from event_runtime import Request
from original_pages import OriginalPages
DATA=OriginalData(ROOT/'original-1.20.4')

class LetterChecks(unittest.TestCase):
    def test_body_is_complete_original_script_and_other_items_are_unchanged(self):
        app=SimpleNamespace(data=DATA)
        row=DATA.tables['Item']['270057']
        text=OriginalPages._bag_item_description(app,'270057',row)
        source=DATA.event('pEvent5807003.json')[11]['text'].partition(':')[2]
        self.assertEqual(row['des']+'\n\n'+re.sub(r'#[0-9]','',source),text)
        self.assertNotIn('#1',text)
        self.assertTrue(text.endswith('（注：图鉴要好好保管！）'))
        for key in ('270018','230001'):
            row=DATA.tables['Item'][key]
            self.assertEqual(row['des'],OriginalPages._bag_item_description(app,key,row))

    def test_real_bag_quest_tab_reads_and_scrolls_without_consumption_or_story_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            previous=os.environ.get('POCKET_NATIVE_SAVE_DIR')
            os.environ['POCKET_NATIVE_SAVE_DIR']=folder
            root=tk.Tk();root.withdraw();app=None
            try:
                app=NativeGame(root,DATA)
                app.state.initialize(1)
                app.state.inventory={'270057':1}
                app.runtime.file,app.runtime.sequence,app.runtime.pending='',[],None
                app.display_request=app.dialogue=app.pending_wait=None
                before=copy.deepcopy(app.state.payload())
                app.open_ui(Request('openui','test',0,{'parameters':{'uiid':46}}))
                app.ui_window.withdraw()
                app.ui_actions['tag_4_Button']()
                self.assertIn('哟，儿子！',app.ui_info.get())
                self.assertIn('图鉴要好好保管！',app.ui_info.get())
                self.assertFalse(any(k.endswith('/use_Button') for k in app.original_page.hits))
                rect=next(r for k,r in app.original_page.rects.items() if k.endswith('/info_Text'))
                out=ROOT/'outputs/verification';out.mkdir(parents=True,exist_ok=True)
                app.ui_base_layer.save(out/'letter-bag-0.2.60.png')
                # A real wheel callback changes the clipped details, not the list.
                for _ in range(8):app.page_wheel(SimpleNamespace(x=(rect[0]+rect[2])/2,y=(rect[1]+rect[3])/2,delta=-120))
                app.ui_base_layer.save(out/'letter-bag-bottom-0.2.60.png')
                self.assertEqual(before,app.state.payload())
                self.assertEqual('',app.runtime.file)
                self.assertEqual(1,app.state.count('270057'))
            finally:
                if app and app.ui_window and app.ui_window.winfo_exists():app.ui_window.destroy()
                for job in root.tk.call('after','info'):root.after_cancel(job)
                root.destroy()
                if previous is None:os.environ.pop('POCKET_NATIVE_SAVE_DIR',None)
                else:os.environ['POCKET_NATIVE_SAVE_DIR']=previous

if __name__=='__main__':unittest.main(verbosity=2)
