"""Original MainUI scene buttons and 0.2-second menu expansion actions.

Function-specific pages remain separate; rendering a button is not proof that
its complete original gameplay exists. See the mechanics evidence ledger.
"""
import time
from tkinter import messagebox
from event_runtime import Request
from mounts import Mounts
from guide import exit_map_id


class SceneUI:
    SHOP_TYPES = (1, 4, 3, 2, 5)  # shop, bank, materials, scrolls, gym
    def __init__(self, app):
        self.app = app
        self.hits = {}
        self.hidden = False
        self.cached_layer = None
        self.cached_key = None
        self.groups = {key: {'value': 0.0, 'start': 0.0, 'target': 0.0, 'clock': 0.0}
                       for key in ('left', 'right', 'up')}

    def value(self, key):
        group = self.groups[key]
        progress = min(1, (time.monotonic()-group['clock'])/.2)
        group['value'] = group['start']+(group['target']-group['start'])*progress
        return group['value']

    def toggle(self, key):
        value = self.value(key)
        group = self.groups[key]
        group.update(start=value, target=0.0 if group['target'] else 1.0, clock=time.monotonic())

    def shop_exits(self):
        result = {}
        for obj in sorted(getattr(self.app.map, 'objects', []), key=lambda o: str(o.get('name', '')).zfill(12)):
            target = obj.get('props', {}).get('toExit')
            if obj.get('group') != 'spriteLayer' or not target:
                continue
            mid = exit_map_id(self.app.data.tables, target)
            kind = int(self.app.data.tables['VillageMap'].get(str(mid), {}).get('shopType', 0))
            if kind > 0:
                result.setdefault(kind, obj)
        return result

    def render(self, frame):
        app = self.app
        left, right, up = (self.value(key) for key in ('left', 'right', 'up'))
        shops = self.shop_exits()
        signature = (left, right, up, self.hidden, app.WIDTH, app.HEIGHT, tuple(shops))
        if self.cached_key == signature and self.cached_layer is not None:
            frame.alpha_composite(self.cached_layer)
            return
        positions = {}
        for i in range(1, 6):
            positions[f'left_right_{i}_Button'] = [72*i*left, 0]
            positions[f'up_left_{i}_Button'] = [-47*i*up, 0]
        for i in range(1, 8):
            positions[f'right_left_{i}_Button'] = [-72*i*right, 0]
        for i in range(1, 4):
            positions[f'right_up_{i}_Button'] = [0, 78*i*right]
        visible = {'left_right_Panel': left > 0, 'right_left_Panel': right > 0,
                   'right_up_Panel': right > 0, 'up_left_Panel': up > 0,
                   'task_Button': right == 0, 'community_Button': right == 0,
                   'timelimitGiftBag_Button': False, 'timelimitGiftBagTimeBg_Image': False,
                   'giftReceive_Button': False, 'giftReceive_Particle': False,
                   'petCatchState_Panel': False, 'playerState_ListView': False,
                   'mapName_ProjectNode': False}
        for index, kind in enumerate(self.SHOP_TYPES, 1):
            visible[f'up_left_{index}_Button'] = kind in shops
        # These embedded notification nodes contain editor sample numbers.
        # Display them only after their real activity counters are connected.
        for name in ('petCanEvolution_Node', 'achievementCanReceived_Node', 'rankChanged_Node',
                     'receivedGift_Node', 'mainRightCanReceived_Node', 'taskCanReceived_Node',
                     'message_Node', 'rechargeCanReceived_Node', 'drawPetFree_Node'):
            visible[name] = False
        if self.hidden:
            def hide_buttons(node):
                if node.get('class') == 'Button':
                    visible[node['name']] = node['name'] == 'uiDisappear_Button'
                for child in node.get('children', []):
                    hide_buttons(child)
            hide_buttons(app.cocos_ui.layout('MainUI')['tree'])
        layer = app.cocos_ui.render('MainUI', (app.WIDTH, app.HEIGHT),
                                    visible=visible, positions=positions)
        self.hits = {key: rect for key, rect in app.cocos_ui.hits.items()
                     if '/' not in key and key.endswith('_Button')}
        self.cached_key, self.cached_layer = signature, layer
        frame.alpha_composite(layer)

    def click(self, x, y):
        for key, rect in self.hits.items():
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                self.action(key)
                return True
        return False

    def action(self, key):
        app = self.app
        toggles = {'mainLeft_Button': 'left', 'mainRight_Button': 'right'}
        if key in toggles:
            self.toggle(toggles[key])
            return
        callbacks = {'save_Button': app.save, 'task_Button': app.tasks_ui,
                     'mainUp_Button': app.guide_toggle,
                     'draw_Button': app.lottery_ui, 'right_left_1_Button': app.bag_ui,
                     'right_left_2_Button': app.pets_ui,
                     'right_left_3_Button': app.illustrated_ui,
                     'right_left_4_Button': app.achievements_ui}
        if key in callbacks:
            callbacks[key]()
            return
        if key.startswith('left_right_'):
            index = int(key.split('_')[2])
            ride = [500001, 500002, 500003, 500004, 500005][index-1]
            mounts = Mounts(app.state)
            if app.state.ride == ride:
                ride = 0
            try:
                mounts.select(ride, app.map.terrain_at(app.x, app.y), int(app.map.info['mapType']))
            except ValueError as error:
                messagebox.showinfo('坐骑', str(error), parent=app.root)
            return
        if key.startswith('up_left_'):
            try:
                app.guide_shop(int(key.split('_')[2]))
                if self.groups['up']['target']:
                    self.toggle('up')
            except ValueError as error:
                messagebox.showinfo('指引', str(error), parent=app.root)
            return
        uiids = {'right_left_5_Button': 26, 'right_up_2_Button': 9,
                 'right_up_3_Button': 12, 'faDaJing_Button': 24}
        if key in uiids:
            app.open_ui(Request('openui', 'scene-menu', 0, {'parameters': {'uiid': uiids[key]}}))
            return
        if key == 'uiDisappear_Button':
            self.hidden = not self.hidden
            return
        # Unsupported pages must never silently consume a click or grant rewards.
        messagebox.showinfo('尚未完成的原版功能', '这个入口的原版交互还在移植，当前不能完成该操作。', parent=app.root)
