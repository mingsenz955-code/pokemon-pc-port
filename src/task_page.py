"""Original TaskUI / TaskItemUI / RewardItemUI inside the game canvas.

TaskUILayer 0x3be5c8: receive is daily-only; selecting main/branch rows
updates descriptions/rewards, it does not issue a navigation command.
"""
from PIL import Image
from csb_render import CocosUI
from daily_tasks import DailyTasks
from game_state import numbers
from task_progress import TaskProgress, required_counts


class TaskPage:
    def __init__(self, app, page='main'):
        self.app = app
        self.ui = CocosUI(app.data)
        self.page = page if page in ('main', 'branch', 'daily') else 'main'
        self.selected = 0
        self.scroll = 0
        self.reward_scroll = 0
        self.info_scroll = 0
        self.info_limit = 0
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
        self.info_scroll = 0
        self.sync()
        self.frame = None
        if getattr(self.app, 'ui_info', None):
            self.app.ui_info.set(self.info())

    def receive(self):
        if not self.rows:
            return
        key, row, status, counts = self.rows[self.selected]
        if self.page != 'daily':
            # Main/branch tasks are submitted by their original NPC talk
            # event. Keep the task page open and explain it instead of
            # silently teleporting or issuing a fabricated reward.
            if getattr(self.app, 'ui_info', None):
                state = '已完成，等待原版NPC结算。' if status == 4 else '尚未完成。'
                self.app.ui_info.set(
                    f'{row["name"]}：{state}请与任务对应的原版NPC对话完成，'
                    '页面不会伪造或直接发放奖励。')
            return
        if status != 4:
            return
        result = DailyTasks(self.app.state).claim(key)
        self.sync()
        self.frame = None
        names = []
        for item_id, count in result['rewards']:
            source = (self.app.data.tables['Item'].get(str(item_id))
                      or self.app.data.tables['Money'].get(str(item_id))
                      or self.app.data.tables['Pet'].get(str(item_id)) or {})
            names.append(f'{source.get("name", item_id)}×{count}')
        if getattr(self.app, 'ui_info', None):
            self.app.ui_info.set('领取成功：' + ('、'.join(names) or '每日任务奖励'))
        self.app.show_reward('每日任务奖励', result['rewards'])

    def info(self):
        if not self.rows:
            return ''
        key, row, status, counts = self.rows[self.selected]
        progress = ' / '.join(f'{counts[i] if i < len(counts) else 0}/{n}'
                              for i, n in enumerate(required_counts(row)))
        text = f'{row["name"]}\n{row["des"]}\n{progress}'
        if not any(numbers(row.get('rewardIds', '0'))):
            # BranchTask 2801/6201 really have no reward rows.  Do not invent
            # an icon or amount: their payout is resolved by the original NPC
            # dialogue event.
            text += '\n（原版任务表未配置奖励；完成条件仍由对应NPC对话结算。）'
        return text

    def render(self):
        self.sync()
        signature = (self.page, self.selected, self.scroll, self.reward_scroll, self.info_scroll, self.pressed, repr(self.rows))
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
            text['progress_BitmapFontLabel'] = f'{len(set(self.app.state.completed_main))}/{len(self.app.state.tables["MainTask"])}'
        elif self.page == 'branch':
            text['progress_BitmapFontLabel'] = f'{len(self.app.state.completed_branch)}/{len(self.app.state.tables["BranchTask"])}'
        else:
            text['progress_BitmapFontLabel'] = f'{DailyTasks(self.app.state).normal_completed()}/7'
        # Only daily tasks are claimed in TaskUI. Main/branch completion is
        # resolved by their original NPC conversation, so no receive node is
        # exposed there (even when the original status is "ready").
        visible['receive_Button'] = bool(
            self.rows and self.page == 'daily' and self.rows[self.selected][2] == 4)
        if self.rows:
            key, row, status, counts = self.rows[self.selected]
            for i, required in enumerate(required_counts(row)[:4], 1):
                visible[f'progress_{i}_Text'] = False
                text[f'progress_{i}_Text'] = f'{counts[i-1] if i <= len(counts) else 0}/{required}'
        frame = self.ui.render('TaskUI', (800, 480), text, visible, resources,
                               pressed={self.pressed: True} if self.pressed else {}, rich_text=('info_Text',))
        self.hits = {k: v for k, v in self.ui.buttons.items() if '/' not in k}
        self.rects = dict(self.ui.rects)
        if self.rows:
            from pet_pages import text_box
            from types import SimpleNamespace
            paper = self.rects['info_bg_Image']
            description = (paper[0]+64, paper[1]+62, paper[2]-56, paper[1]+142)
            self.info_limit = text_box(SimpleNamespace(layer=frame), description,
                     self.rows[self.selected][1]['des'], self.ui.font('', 15), self.info_scroll)
            self.hits['description'] = description
            progress = '  '.join(f'{counts[i] if i < len(counts) else 0}/{required}'
                                for i, required in enumerate(required_counts(row)) if required > 0)
            text_box(SimpleNamespace(layer=frame),
                     (description[0], paper[1]+145, description[2], paper[1]+166),
                     progress, self.ui.font('', 16))
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
        top += 9
        # Keep every reward inside the paper, above the claim control.
        bottom = min(bottom, round(self.rects['reward_Panel'][3]))
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
            art = self.ui.render('RewardItemUI', (96, 104), canvas_size=(96, 104),
                                 text={'count_BitmapFontLabel': str(count), 'name_Text': source.get('name', '')},
                                 resources={'icon_Image': icon} if icon else None,
                                 positions={'iconBg_Image': (38, 66), 'count_BitmapFontLabel': (8, 14)})
            clip.alpha_composite(art, ((index % 2)*96, round((index//2)*110-self.reward_scroll)))
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
            self.info_scroll = 0
        elif key and key.startswith('tag_'):
            self.select_page(('main', 'branch', 'daily')[int(key.split('_')[1])-1])
        elif key == 'receive_Button':
            self.receive()
        elif key == 'close_Button':
            self.app.close_ui('no')

    def reward_limit(self):
        if not self.rows:
            return 0
        count = len([i for i in numbers(self.rows[self.selected][1].get('rewardIds', '0')) if i])
        height = self.hits.get('rewards', (0, 0, 0, 109))
        return max(0, max(0, ((count+1)//2)-1)*110+104-(height[3]-height[1])) if count else 0

    def wheel(self, delta, x=None, y=None):
        if x is not None and self.hit(x, y) == 'description':
            self.info_scroll = max(0, min(self.info_scroll-delta*24, self.info_limit))
        elif x is not None and self.hit(x, y) == 'rewards':
            self.reward_scroll = max(0, min(self.reward_scroll-delta*44, self.reward_limit()))
        else:
            self.scroll = max(0, min(self.scroll-delta*44, max(0, len(self.rows)*44-319)))
        self.frame = None
