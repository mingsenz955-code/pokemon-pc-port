"""Original TaskUI / TaskItemUI / RewardItemUI inside the game canvas.

TaskUILayer 0x3be5c8: receive is daily-only; selecting main/branch rows
updates descriptions/rewards, it does not issue a navigation command.
"""
from PIL import Image
from csb_render import CocosUI
from daily_tasks import DailyTasks
from game_state import numbers
from task_progress import TaskProgress


class TaskPage:
    def __init__(self, app, page='main'):
        self.app = app
        self.ui = CocosUI(app.data)
        self.page = page if page in ('main', 'branch', 'daily') else 'main'
        self.selected = 0
        self.scroll = 0
        self.reward_scroll = 0
        self.pressed = None
        self.drag = None
        self.frame = None
        self.signature = None
        self.hits = {}
        self.rows = []
        self.sync()

    def sync(self):
        state = self.app.state
        TaskProgress(state).update()
        if self.page == 'main':
            key = str(state.main_task)
            row = state.tables['MainTask'].get(key)
            self.rows = [(key, row, state.main_state, state.task_counts.get('main:'+key, []))] if row else []
        elif self.page == 'branch':
            self.rows = [(str(key), state.tables['BranchTask'][str(key)], status,
                          state.task_counts.get('branch:'+str(key), []))
                         for key, status in sorted(state.branch_states.items(), key=lambda p: int(p[0]))
                         if status in (3, 4, 5) and str(key) in state.tables['BranchTask']]
        else:
            daily = DailyTasks(state)
            self.rows = [(r['id'], state.tables['DailyTask'][r['id']],
                          5 if r['claimed'] else 4 if r['ready'] else 3, [r['progress']])
                         for r in daily.status()]
        self.selected = min(self.selected, max(0, len(self.rows)-1))
        self.scroll = max(0, min(self.scroll, max(0, len(self.rows)*44-319)))

    def select_page(self, page):
        self.page, self.selected, self.scroll, self.reward_scroll = page, 0, 0, 0
        self.sync()
        self.frame = None
        if getattr(self.app, 'ui_info', None):
            self.app.ui_info.set(self.info())

    def receive(self):
        if self.page != 'daily' or not self.rows:
            return  # Original receiveButtonRespond is not a task-guide button.
        key, row, status, counts = self.rows[self.selected]
        if status != 4:
            return
        DailyTasks(self.app.state).claim(key)
        self.sync()
        self.frame = None

    def info(self):
        if not self.rows:
            return ''
        key, row, status, counts = self.rows[self.selected]
        progress = ' / '.join(f'{counts[i] if i < len(counts) else 0}/{n}'
                              for i, n in enumerate(numbers(row['counts'])))
        return f'{row["name"]}\n{row["des"]}\n{progress}'

    def render(self):
        self.sync()
        signature = (self.page, self.selected, self.scroll, self.reward_scroll, self.pressed, repr(self.rows))
        if self.frame is not None and signature == self.signature:
            return self.frame
        self.signature = signature
        text = {'info_Text': '', 'progress_BitmapFontLabel': ''}
        visible = {f'{name}Item_ListView': name == self.page for name in ('main', 'branch', 'daily')}
        resources = {f'tag_{i}_Button': 'UI/tag_selected.png' if self.page == page else 'UI/tag_unselected.png'
                     for i, page in enumerate(('main', 'branch', 'daily'), 1)}
        for i in range(1, 5):
            visible[f'progress_{i}_Text'] = False
        if self.page == 'main':
            text['progress_BitmapFontLabel'] = f'{self.app.state.main_task}/{len(self.app.state.tables["MainTask"])}'
        elif self.page == 'branch':
            text['progress_BitmapFontLabel'] = f'{len(self.app.state.completed_branch)}/{len(self.app.state.tables["BranchTask"])}'
        else:
            text['progress_BitmapFontLabel'] = f'{DailyTasks(self.app.state).normal_completed()}/7'
        visible['receive_Button'] = bool(self.page == 'daily' and self.rows and self.rows[self.selected][2] != 5)
        if self.rows:
            key, row, status, counts = self.rows[self.selected]
            text['info_Text'] = row['des']
            for i, required in enumerate(numbers(row['counts'])[:4], 1):
                visible[f'progress_{i}_Text'] = True
                text[f'progress_{i}_Text'] = f'{counts[i-1] if i <= len(counts) else 0}/{required}'
        frame = self.ui.render('TaskUI', (800, 480), text, visible, resources,
                               pressed={self.pressed: True} if self.pressed else {}, rich_text=('info_Text',))
        self.hits = {k: v for k, v in self.ui.buttons.items() if '/' not in k}
        self.rects = dict(self.ui.rects)
        left, top, right, bottom = [round(v) for v in self.rects[self.page+'Item_ListView']]
        viewport = Image.new('RGBA', (right-left, bottom-top))
        for index, (key, row, status, counts) in enumerate(self.rows):
            y = index*44-self.scroll
            if y+44 <= 0 or y >= viewport.height:
                continue
            art = self.ui.render('TaskItemUI', (286, 44),
                {'itemName_Text': row['name'], 'id_BitmapFontLabel': f'{key}.'},
                {'selected_Image': index == self.selected, 'received_Image': self.page == 'daily' and status == 5,
                 'submited_Image': self.page != 'daily' and status == 5,
                 'doneBg_Image': status != 5, 'done_Image': status == 4})
            viewport.alpha_composite(art, (0, round(y)))
            self.hits[f'task_row_{index}'] = (left, max(top, top+y), right, min(bottom, top+y+44))
        frame.alpha_composite(viewport, (left, top))
        if self.rows:
            self.draw_rewards(frame, self.rows[self.selected][1])
        # Disabled receive uses the original node, with its brightness reduced.
        if visible['receive_Button'] and self.rows[self.selected][2] != 4:
            rect = tuple(round(v) for v in self.rects['receive_Button'])
            tile = frame.crop(rect).convert('LA').convert('RGBA')
            frame.alpha_composite(tile, rect[:2])
        self.frame = frame
        return frame

    def draw_rewards(self, frame, row):
        button = self.rects.get('receive_Button')
        button_rect = tuple(round(v) for v in button) if button else None
        button_image = frame.crop(button_rect) if button_rect else None
        rect = self.rects['reward_ListView']
        left, top, right, bottom = [round(v) for v in rect]
        clip = Image.new('RGBA', (right-left, bottom-top))
        self.hits['rewards'] = (left, top, right, bottom)
        for index, (key, count) in enumerate(zip(numbers(row.get('rewardIds', '0')), numbers(row.get('rewardCounts', '0')))):
            if not key or not count:
                continue
            source = next((self.app.state.tables[t][str(key)] for t in ('Money', 'Item', 'Pet')
                           if str(key) in self.app.state.tables.get(t, {})), {})
            icon = source.get('littleIconTexture') or source.get('texture') or source.get('icon', '')
            if icon:
                path = self.app.data.image_paths.get(icon)
                if path:
                    icon = str(path.relative_to(self.app.data.assets)).replace('\\', '/')
                    if icon.startswith('res/'):
                        icon = icon[4:]
            art = self.ui.render('RewardItemUI', (160, 76),
                                 {'count_BitmapFontLabel': str(count), 'name_Text': source.get('name', '')},
                                 resources={'icon_Image': icon} if icon else None)
            clip.alpha_composite(art, (0, round(index*76-self.reward_scroll)))
        frame.alpha_composite(clip, (left, top))
        if button_image is not None:
            frame.alpha_composite(button_image, button_rect[:2])

    def hit(self, x, y):
        self.render()
        for key, rect in self.hits.items():
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                return key

    def press(self, x, y):
        self.pressed = self.hit(x, y)
        self.drag = (x, y, self.reward_scroll if self.pressed == 'rewards' else self.scroll, False)
        self.frame = None

    def motion(self, x, y):
        if self.drag and self.pressed and (self.pressed.startswith('task_row_') or self.pressed == 'rewards'):
            sx, sy, scroll, moved = self.drag
            if abs(y-sy) > 5 or moved:
                if self.pressed == 'rewards':
                    self.reward_scroll = max(0, min(scroll+sy-y, self.reward_limit()))
                else:
                    self.scroll = max(0, min(scroll+sy-y, max(0, len(self.rows)*44-319)))
                self.drag = (sx, sy, scroll, True)
                self.frame = None

    def release(self, x, y):
        key = self.hit(x, y)
        pressed, drag = self.pressed, self.drag
        self.pressed, self.drag, self.frame = None, None, None
        if key != pressed or (drag and drag[3]):
            return
        if key and key.startswith('task_row_'):
            self.selected = int(key.rsplit('_', 1)[1])
            self.reward_scroll = 0
        elif key and key.startswith('tag_'):
            self.select_page(('main', 'branch', 'daily')[int(key.split('_')[1])-1])
        elif key == 'receive_Button':
            self.receive()
        elif key == 'close_Button':
            self.app.close_ui('no')

    def reward_limit(self):
        if not self.rows:
            return 0
        return max(0, len([i for i in numbers(self.rows[self.selected][1].get('rewardIds', '0')) if i])*76-151)

    def wheel(self, delta, x=None, y=None):
        if x is not None and self.hit(x, y) == 'rewards':
            self.reward_scroll = max(0, min(self.reward_scroll-delta*44, self.reward_limit()))
        else:
            self.scroll = max(0, min(self.scroll-delta*44, max(0, len(self.rows)*44-319)))
        self.frame = None
