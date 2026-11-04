"""Original MainUI scene buttons and 0.2-second menu expansion actions.

Function-specific pages remain separate; rendering a button is not proof that
its complete original gameplay exists. See the mechanics evidence ledger.
"""
import time
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageFilter
from event_runtime import Request
from mounts import Mounts
from offline_tutorials import REMOVED_SCENE_BUTTONS
from guide import exit_map_id


def mailbox_icon(app, size, unread):
    icon = Image.new('RGBA', (144, 156))
    bubble = app.data.image('res/UI/button_ui_status.png')
    icon.alpha_composite(bubble.resize((130, 130), Image.Resampling.LANCZOS), (7, 12))
    draw = ImageDraw.Draw(icon)
    draw.rounded_rectangle((26, 42, 118, 104), radius=10, fill='#7a4325', outline='#fff3ca', width=3)
    draw.rounded_rectangle((30, 45, 114, 99), radius=7, fill='#ffe0a0', outline='#ad692a', width=3)
    draw.polygon([(32, 95), (72, 65), (112, 95)], fill='#ffc972')
    draw.polygon([(32, 49), (72, 80), (112, 49)], fill='#fff2cb')
    draw.line([(32, 49), (72, 80), (112, 49)], fill='#b87638', width=4)
    draw.ellipse((62, 70, 82, 90), fill='#c62e32', outline='#7c2226', width=2)
    draw.ellipse((65, 73, 71, 78), fill='#ff9a84')
    glyphs = Image.new('L', (100, 52))
    ImageDraw.Draw(glyphs).text((50, 25), '邮件', font=app.cocos_ui.font('', 34),
                                anchor='mm', fill=255, stroke_width=2, stroke_fill=255)
    glyphs = glyphs.crop(glyphs.getbbox()).resize((53, 24), Image.Resampling.LANCZOS)
    label = Image.new('L', (65, 36))
    label.paste(glyphs, (6, 6))
    gradient = Image.new('RGBA', label.size)
    gold = ImageDraw.Draw(gradient)
    for y in range(label.height):
        green = 247-round(70*y/(label.height-1))
        gold.line((0, y, label.width, y), fill=(255, green, 57, 255))
    outline = Image.new('RGBA', label.size, '#5d2b12')
    outline.putalpha(label.filter(ImageFilter.MaxFilter(9)))
    icon.alpha_composite(outline, (39, 111))
    gradient.putalpha(label)
    icon.alpha_composite(gradient, (39, 111))
    if unread:
        badge = app.data.image('res/UI/button_about.png')
        icon.alpha_composite(badge.resize((38, 38), Image.Resampling.LANCZOS), (100, 9))
    return icon.resize(size, Image.Resampling.LANCZOS)


class SceneUI:
    SHOP_TYPES = (1, 4, 3, 2, 5)  # shop, bank, materials, scrolls, gym
    def __init__(self, app):
        self.app = app
        self.hits = {}
        self.hidden = False
        self.cached_layer = None
        self.cached_key = None
        self.tip = None
        self.ride_buttons = {}
        def collect(node):
            if node.get('name', '').startswith('left_right_') and node.get('class') == 'Button':
                self.ride_buttons[node['name']] = int(node['tag'])
            for child in node.get('children', []):
                collect(child)
        collect(app.cocos_ui.layout('MainUI')['tree'])
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
        self.cached_key = None
        if key == 'left' and not group['target']:
            self.hits = {k: v for k, v in self.hits.items() if k not in self.ride_buttons}

    def fold_rides(self):
        group = self.groups['left']
        group.update(start=self.value('left'), target=0.0, clock=time.monotonic())
        # Native leftButtonsFold disables touches immediately, before MoveTo ends.
        self.hits = {k: v for k, v in self.hits.items() if k not in self.ride_buttons}
        self.cached_key = None

    def show_tip(self, text):
        # TipsUiLayer::showTips: delay one second, fade out over one second.
        self.tip = (str(text), time.monotonic())

    def render_tip(self, frame):
        if self.tip is None:
            return
        text, started = self.tip
        elapsed = time.monotonic()-started
        if elapsed >= 2:
            self.tip = None
            return
        ui = self.app.cocos_ui
        width = min(760, max(100, ui.font('', 30).getlength(text)+34))
        layer = ui.render('TipsUiNode', frame.size, canvas_size=(800, 480),
            text={'tip_Text': text}, auto_text=('tip_Text',),
            positions={'bg_Image': (400, 240), 'tip_Text': (width/2, 29.5)},
            sizes={'bg_Image': (width, 59)},
            alphas={'Node': round(255*min(1, 2-elapsed))})
        frame.alpha_composite(layer)

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
        owned = tuple(int(key) for key in getattr(getattr(app, 'state', None), 'rides', ()))
        maildata=app.state.activities.get('mailbox',{})
        unread=sum(m['id'] not in maildata.get('read',[]) for m in maildata.get('messages',[])
                   if m.get('to')=='all' or maildata.get('player_id') in m.get('to',[]))
        signature = (unread,left, right, up, self.hidden, app.WIDTH, app.HEIGHT, tuple(shops), owned)
        if self.cached_key == signature and self.cached_layer is not None:
            frame.alpha_composite(self.cached_layer)
            return
        positions = {}
        alphas = {}
        for i in range(1, 6):
            positions[f'left_right_{i}_Button'] = [72*i*left, 0]
            # CSB authors these at opacity zero; native initialization sets 255.
            alphas[f'left_right_{i}_Button'] = 255
            positions[f'up_left_{i}_Button'] = [-47*i*up, 0]
            alphas[f'up_left_{i}_Button'] = round(255*up)
        for i in range(1, 8):
            positions[f'right_left_{i}_Button'] = [-72*i*right, 0]
            alphas[f'right_left_{i}_Button'] = round(255*right)
        for i in range(1, 4):
            positions[f'right_up_{i}_Button'] = [0, 78*i*right]
            alphas[f'right_up_{i}_Button'] = round(255*right)
        visible = {'left_right_Panel': left > 0, 'right_left_Panel': right > 0,
                   'right_up_Panel': right > 0, 'up_left_Panel': up > 0,
                   'task_Button': right == 0, 'community_Button': False,
                   # The four-arrow HUD hide/show button sits over the
                   # illustrated-book icon when the right menu is expanded.
                   'uiDisappear_Button': right == 0,
                   'rechargeReward_Button': False, 'timelimitGiftBag_Button': False, 'timelimitGiftBagTimeBg_Image': False,
                   # Single-player PC port: no online rank, gift-code exchange or
                   # Bluetooth battle entry points. Keep the original slots hidden
                   # instead of leaving dead buttons in the expanded menu.
                   'right_left_5_Button': False, 'right_left_6_Button': False,
                   'right_left_7_Button': False,
                   'giftReceive_Button': False, 'giftReceive_Particle': False,
                   'petCatchState_Panel': False, 'playerState_ListView': False,
                   'mapName_ProjectNode': False}
        visible.update({key: False for key in REMOVED_SCENE_BUTTONS})
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
            # Keep the four-arrow toggle hidden while the right menu is open.
            visible['uiDisappear_Button'] = right == 0
        layer = app.cocos_ui.render('MainUI', (app.WIDTH, app.HEIGHT),
                                    visible=visible, positions=positions, alphas=alphas,
                                    bright={key: ride in owned for key, ride in self.ride_buttons.items()})
        self.hits = {key: rect for key, rect in app.cocos_ui.hits.items()
                     if '/' not in key and key.endswith('_Button')
                     and visible.get(key, True) is not False
                     and alphas.get(key, 255) > 0
                     and (key not in self.ride_buttons or self.groups['left']['target'] == 1)}
        if 'task_Button' in self.hits:
            left_edge, top, right_edge, bottom = self.hits['task_Button']
            width, height = round(right_edge-left_edge), round(bottom-top)
            gap = round(3*app.WIDTH/800)
            x = left_edge-width-gap
            layer.alpha_composite(mailbox_icon(app, (width, height), unread), (round(x), round(top)))
            self.hits['mailbox_Button'] = (x, top, x+width, top+height)
        self.cached_key, self.cached_layer = signature, layer
        frame.alpha_composite(layer)

    def click(self, x, y):
        # Match painter order: the main riding button covers the folding icons.
        for key, rect in reversed(tuple(self.hits.items())):
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
        callbacks = {'mailbox_Button': lambda: app.mailbox_ui(), 'save_Button': app.save_ui, 'task_Button': app.tasks_ui,
                     'mainUp_Button': app.guide_toggle,
                     'draw_Button': app.lottery_ui, 'store_Button': app.store_ui,
                     'rechargeReward_Button': app.recharge_ui,
                     'right_left_1_Button': app.bag_ui,
                     'right_left_2_Button': app.pets_ui,
                     'right_left_3_Button': app.illustrated_ui,
                     'right_left_4_Button': app.achievements_ui,
                     'right_up_1_Button': lambda: app.open_ui(Request(
                         'openui', 'scene-system', 0, {'parameters': {'uiid': 65}})),
                     'ad_Button': app.recharge_ui}
        if key in callbacks:
            callbacks[key]()
            return
        if key in self.ride_buttons:
            if not self.groups['left']['target']:
                return
            self.fold_rides()
            ride = self.ride_buttons[key]
            mounts = Mounts(app.state)
            if app.state.ride == ride:
                ride = 0
            try:
                if ride == 0 and app.map.sprite_blocked(app.x, app.y):
                    raise ValueError('此处不能收回坐骑')
                mounts.select(ride, app.map.terrain_at(app.x, app.y), int(app.map.info['mapType']))
            except ValueError as error:
                row = app.data.tables['Ride'].get(str(ride), {})
                if ride and ride not in [int(k) for k in app.state.rides] and not app.state.trial_ride:
                    app.open_ui(Request('openui', 'ride-tip', 1,
                        {'parameters': {'uiid': 51, 'text': row.get('des', str(error))}}))
                else:
                    self.show_tip(str(error))
            return
        if key.startswith('up_left_'):
            try:
                app.guide_shop(int(key.split('_')[2]))
                if self.groups['up']['target']:
                    self.toggle('up')
            except ValueError as error:
                app.game_tip(str(error))
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
        app.game_tip('这个入口的原版交互还在移植，当前不能完成该操作。')
