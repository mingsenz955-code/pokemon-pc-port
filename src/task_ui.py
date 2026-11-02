"""Interactive task page composed from original TaskUI/TaskItemUI/RewardItemUI.

Main/branch quests are submitted by their plot scripts. Only daily quests have
a claim button here, matching TaskUILayer::refreshSubmitButtonState.
"""
from PIL import Image, ImageDraw
from daily_tasks import DailyTasks, prerequisites
from game_state import numbers
from task_progress import TaskProgress


class TaskUI:
    def __init__(self, app):
        self.app = app
        self.tab = 1
        self.selected = None
        self.scroll = 0
        self.reward_scroll = 0
        self.reward_rect = None
        self.hits = {}
        self.signature = None
        self.frame = None

    def rows(self):
        state = self.app.state
        if self.tab == 1:
            row = state.tables['MainTask'].get(str(state.main_task))
            return [(str(state.main_task), row, state.main_state)] if row else []
        if self.tab == 2:
            result = []
            for key, row in state.tables['BranchTask'].items():
                status = state.branch_states.get(key, 2 if prerequisites(state, row) else 1)
                if status >= 2:
                    result.append((key, row, status))
            return sorted(result, key=lambda entry: int(entry[0]))
        daily = DailyTasks(state).refresh()
        return [(key, row, daily['states'][key])
                for key, row in sorted(state.tables['DailyTask'].items(), key=lambda p: int(p[0]))
                if daily['states'][key] >= 2]

    def counts(self, key, row, status):
        state = self.app.state
        required = numbers(row['counts'])
        if self.tab == 3:
            actual = DailyTasks(state).refresh()['counts'].get(key, [0]*len(required))
        else:
            category = 'main' if self.tab == 1 else 'branch'
            actual = state.task_counts.get(f'{category}:{key}', [0]*len(required))
        return [min(a, b) for a, b in zip(actual, required)], required

    def progress_label(self):
        state = self.app.state
        if self.tab == 1:
            return f'{state.main_task}/{len(state.tables["MainTask"])}'
        if self.tab == 2:
            return f'{len(state.completed_branch)}/{len(state.tables["BranchTask"])}'
        daily = DailyTasks(state).refresh()
        return f'{sum(v == 5 for v in daily["states"].values())}/{len(state.tables["DailyTask"])}'

    def render(self):
        app, state = self.app, self.app.state
        TaskProgress(state).update()
        rows = self.rows()
        keys = [entry[0] for entry in rows]
        if self.selected not in keys:
            self.selected = keys[0] if keys else None
        chosen = next((entry for entry in rows if entry[0] == self.selected), None)
        signature = (self.tab, self.selected, self.scroll, self.reward_scroll, repr(rows), repr(state.task_counts),
                     repr(state.activities.get('daily_tasks')), self.progress_label())
        if self.frame is not None and self.signature == signature:
            return self.frame
        self.signature = signature
        text = {'progress_BitmapFontLabel': self.progress_label(),
                'info_Text': chosen[1]['des'] if chosen else '',
                **{f'progress_{i}_Text': '' for i in range(1, 5)}}
        visible = {'mainItem_ListView': self.tab == 1, 'branchItem_ListView': self.tab == 2,
                   'dailyItem_ListView': self.tab == 3,
                   'receive_Button': bool(self.tab == 3 and chosen and chosen[2] != 5)}
        if chosen:
            actual, required = self.counts(*chosen)
            for index, (count, target) in enumerate(zip(actual, required), 1):
                text[f'progress_{index}_Text'] = f'{count}/{target}'
        resources = {f'tag_{i}_Button': 'UI/tag_selected.png' if self.tab == i else ''
                     for i in range(1, 4)}
        frame = app.cocos_ui.render('TaskUI', (app.WIDTH, app.HEIGHT), text, visible, resources)
        rects = dict(app.cocos_ui.rects)
        self.hits = {k: v for k, v in app.cocos_ui.hits.items()
                     if '/' not in k and k.endswith('_Button')}
        if chosen and chosen[2] != 4 and self.tab == 3:
            rect = self.hits.get('receive_Button')
            if rect:
                ImageDraw.Draw(frame, 'RGBA').rectangle(rect, fill=(40, 40, 40, 120))
        list_name = {1: 'mainItem_ListView', 2: 'branchItem_ListView', 3: 'dailyItem_ListView'}[self.tab]
        left, top, right, bottom = rects[list_name]
        row_height = 44*app.HEIGHT/480
        capacity = max(1, int((bottom-top)//row_height))
        self.scroll = max(0, min(self.scroll, max(0, len(rows)-capacity)))
        for index, (key, row, status) in enumerate(rows[self.scroll:self.scroll+capacity]):
            y = round(top+index*row_height)
            item = app.cocos_ui.render('TaskItemUI', (round(right-left), round(row_height)),
                text={'itemName_Text': row['name'], 'id_BitmapFontLabel': key+'.'},
                visible={'selected_Image': key == self.selected, 'received_Image': status == 3,
                         'doneBg_Image': status == 4, 'submited_Image': status == 5})
            frame.alpha_composite(item, (round(left), y))
            self.hits['row:'+key] = (left, y, right, y+row_height)
        if chosen:
            left, top, right, bottom = rects['reward_ListView']
            self.reward_rect = (left, top, right, bottom)
            scale_x, scale_y = app.WIDTH/800, app.HEIGHT/480
            rewards = list(zip(numbers(chosen[1]['rewardIds']), numbers(chosen[1]['rewardCounts'])))
            self.reward_scroll = max(0, min(self.reward_scroll, max(0, len(rewards)-1)))
            for index, (key, count) in enumerate(rewards[self.reward_scroll:]):
                if not key or not count:
                    continue
                row = state.tables['Money'].get(str(key)) or state.tables['Item'].get(str(key))
                if row:
                    texture = row.get('littleIconTexture', row.get('texture', ''))
                    icon = 'UI/'+texture
                    name = row['name']
                elif str(key) in state.tables['Pet']:
                    pet = state.tables['Pet'][str(key)]
                    icon, name = '', pet['name']
                else:
                    continue
                image = app.cocos_ui.render('RewardItemUI', (round(160*scale_x), round(76*scale_y)),
                    text={'name_Text': name, 'count_BitmapFontLabel': 'X'+str(count)},
                    resources={'icon_Image': icon})
                y = round(top+index*76*scale_y)
                if y >= bottom:
                    break
                if y+image.height > bottom:
                    image = image.crop((0, 0, image.width, max(1, round(bottom-y))))
                frame.alpha_composite(image, (round(left), y))
        self.frame = frame
        return frame

    def wheel(self, delta, x=None, y=None):
        rect = self.reward_rect
        if rect and x is not None and rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
            self.reward_scroll += -1 if delta > 0 else 1
        else:
            self.scroll += -1 if delta > 0 else 1
        self.signature = None

    def click(self, x, y):
        self.render()
        for key, rect in self.hits.items():
            if not (rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]):
                continue
            if key == 'close_Button':
                self.app.task_page = None
                self.app.ui_open = False
                self.app.autosave()
            elif key.startswith('tag_'):
                self.tab = int(key.split('_')[1])
                self.selected, self.scroll = None, 0
                self.reward_scroll = 0
            elif key.startswith('row:'):
                self.selected = key[4:]
                self.reward_scroll = 0
            elif key == 'receive_Button' and self.tab == 3 and self.selected:
                current = DailyTasks(self.app.state).refresh()
                if current['states'].get(self.selected) == 4:
                    DailyTasks(self.app.state).claim(self.selected)
                    self.app.save()
            self.signature = None
            return
