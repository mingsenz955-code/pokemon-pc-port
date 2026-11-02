"""Native battle presentation using the recovered Cocos Studio battle layouts.

The HUD is the original BattleMainUI; the command wheel is the original
BattleButtonMenuNode / BattleSkillMenuNode / BattleItemMenuNode. Dynamic text
and HP/energy fills are drawn over those layouts, and pet art comes from the
original Spine package rather than from screenshots.
"""
from __future__ import annotations
import time

from PIL import Image, ImageDraw, ImageFont

W, H = 1024, 576
FONT = 'C:/Windows/Fonts/msyh.ttc'


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def cover(image, size):
    if image is None:
        return Image.new('RGBA', size, (28, 34, 44, 255))
    ratio = max(size[0]/image.width, size[1]/image.height)
    resized = image.resize((max(1, round(image.width*ratio)),
                            max(1, round(image.height*ratio))), Image.Resampling.LANCZOS)
    left = (resized.width-size[0])//2
    top = (resized.height-size[1])//2
    return resized.crop((left, top, left+size[0], top+size[1]))


class BattleUI:
    def __init__(self, app, battle):
        self.app = app
        self.battle = battle
        self.screen = 'main'
        self.hits = {}
        self.frame = None
        self.notice = ''
        self.page = 0
        self.ball_page = 0
        self.selected = None
        self._hud_rects = {}
        self.target_hits = {}
        self.item_filter = None
        self.info = ''
        self.animation_clock = time.monotonic()
        self.visual_queue = []
        self.visual_started = self.animation_clock
        self.visual_units = {'player': battle.player_active, 'enemy': battle.enemy_active}
        self.before_units = dict(self.visual_units)

    # -- HUD ----------------------------------------------------------------
    def _hud_layer(self, enemy):
        side = 'enemy' if enemy else 'mine'
        active = self.battle.enemy_active if enemy else self.battle.player_active
        if not active:
            return None
        petrow = self.app.data.tables['Pet'][active.pet.species]
        text = {
            f'{side}_name_Text': active.name,
            'lv_BitmapFontLabel': str(active.pet.level),
            'hp_BitmapFontLabel': f'{active.hp}/{active.max_hp}',
            f'{side}FightPercent_BitmapFontLabel': f'{active.hp*100//active.max_hp}%',
        }
        if not enemy:
            text['energy_BitmapFontLabel'] = f'{active.energy}/{active.max_energy}'
        visible = {'enemy_Panel': enemy, 'mine_Panel': not enemy,
                   'enemyCount_Panel': False, 'catched_Sprite': False,
                   'finded_Sprite': False, 'chat_Panel': False,
                   'leftButtons_Panel': False}
        relation = int(petrow.get('restraint', 3) or 3)
        kind = {1: 'life', 2: 'energy', 3: 'power', 4: 'defence',
                5: 'speed', 6: 'all'}.get(relation, 'power')
        resources = {'kindIcon_Sprite': f'UI/pet_kind_{kind}.png'}
        layer = self.app.cocos_ui.render('BattleMainUI', (W, H), text, visible, resources)
        for name in ('mineMenuPos_Panel', 'enemyMenuPos_Panel'):
            if name in self.app.cocos_ui.rects:
                self.target_hits[name] = self.app.cocos_ui.rects[name]
        self._hud_rects[side] = {
            key: value for key, value in self.app.cocos_ui.rects.items()
            if key.endswith('/hp_LoadingBar') or key.endswith('/energy_LoadingBar')}
        return layer

    def _bar(self, draw, rect, ratio, color):
        if not rect:
            return
        x1, y1, x2, y2 = [round(v) for v in rect]
        draw.rectangle((x1, y1, x2, y2), fill=(20, 22, 24, 210))
        width = max(0, round((x2-x1)*max(0, min(1, ratio))))
        if width:
            draw.rectangle((x1, y1, x1+width, y2), fill=color)

    def _crop_layout(self, name, text=None, visible=None, resources=None, offset=(0, 0)):
        layer = self.app.cocos_ui.render(name, (W, H), text or {}, visible or {}, resources or {},
                                         offset)
        bbox = layer.getbbox()
        if not bbox:
            return None, (0, 0), {}
        crop = layer.crop(bbox)
        hits = {}
        for key, (x1, y1, x2, y2) in self.app.cocos_ui.hits.items():
            # The renderer exposes both qualified paths and short aliases.
            # Only actionable short names belong in this dispatch table.
            if '/' in key or not ('Button' in key):
                continue
            if x1 >= bbox[0] and y1 >= bbox[1] and x2 <= bbox[2] and y2 <= bbox[3]:
                hits[key] = (x1-bbox[0], y1-bbox[1], x2-bbox[0], y2-bbox[1])
        return crop, bbox[:2], hits

    def _paste(self, frame, layer, at, hits):
        if layer is None:
            return
        frame.alpha_composite(layer, at)
        for key, rect in hits.items():
            self.hits[key] = (rect[0]+at[0], rect[1]+at[1],
                              rect[2]+at[0], rect[3]+at[1])

    def _label(self, draw, xy, text, size=16, fill=(255, 255, 255, 255), anchor='la'):
        draw.text(xy, text, font=font(size), fill=fill, anchor=anchor,
                  stroke_width=2, stroke_fill=(0, 0, 0, 220))

    # -- frame ---------------------------------------------------------------
    def render(self):
        self.advance_visual()
        animation_frame = int((time.monotonic()-self.animation_clock)*20)
        signature = (self.screen, self.page, self.ball_page, self.notice, self.info,
                     animation_frame,
                     self.item_filter, repr(self.selected), self.battle.result,
                     self.battle.player_index, self.battle.enemy_index,
                     tuple(self.battle.messages), repr(getattr(self.app, 'battle_tips', [])),
                     repr(self.app.state.inventory),
                     tuple((u.hp, u.energy, repr(u.buffs), u.pet.level) for u in
                           self.battle.player+self.battle.enemy))
        if self.frame is not None and getattr(self, '_signature', None) == signature:
            return self.frame
        self._signature = signature
        frame = Image.new('RGBA', (W, H), (20, 24, 30, 255))
        land = str(getattr(getattr(self.app, 'map', None), 'info', {}).get('landType', '1'))
        background = None
        for candidate in (land, '1', '2'):
            try:
                background = self.app.data.image(f'res/UI/image_battleground{candidate}.png')
                break
            except (KeyError, OSError):
                continue
        if background is None:
            background = getattr(self.app, 'background', None)
        frame.alpha_composite(cover(background, (W, H)))
        frame.alpha_composite(Image.new('RGBA', (W, H), (8, 10, 14, 60)))
        units = self.visual_units if self.visual_queue else {
            'player': self.battle.player_active, 'enemy': self.battle.enemy_active}
        self._draw_pet(frame, units['enemy'], (round(W*.74), round(H*.34)), 235, True)
        self._draw_pet(frame, units['player'], (round(W*.26), round(H*.66)), 250, False)
        for layer in (self._hud_layer(True), self._hud_layer(False)):
            if layer:
                frame.alpha_composite(layer)
        draw = ImageDraw.Draw(frame, 'RGBA')
        self._draw_bars(draw)
        self._draw_status(draw, self.battle.enemy_active, True)
        self._draw_status(draw, self.battle.player_active, False)
        self._draw_team(draw)
        self.hits = {}
        if self.visual_queue:
            pass
        elif self.battle.result:
            self._draw_result(frame, draw)
        elif self.screen == 'main':
            pass  # Original: tap own pet for items, opponent for skills.
        elif self.screen == 'commands':
            self._draw_main_menu(frame)
        elif self.screen == 'skills':
            self._draw_skill_menu(frame)
        elif self.screen == 'items':
            self._draw_item_menu(frame, balls=False)
        elif self.screen == 'balls':
            self._draw_item_menu(frame, balls=True)
        elif self.screen == 'pets':
            self._draw_pet_menu(frame, draw)
        elif self.screen == 'confirm':
            self._draw_confirm(frame, draw)
        self._draw_log(frame, draw)
        if self.notice:
            draw.rectangle((40, H-150, W-40, H-118), fill=(0, 0, 0, 190))
            self._label(draw, (W//2, H-134), self.notice, 17, anchor='mm')
        if getattr(self.app, 'battle_tips', None):
            draw.rectangle((40, 82, W-40, 124), fill=(0, 0, 0, 185))
            self._label(draw, (W//2, 103), self.app.battle_tips[-1], 18, anchor='mm')
        if self.info:
            layer, _, _ = self._crop_layout('SkillInfoNode', {'info_Text': self.info},
                                            offset=(W*.35, H*.35))
            if layer:
                frame.alpha_composite(layer, ((W-layer.width)//2, (H-layer.height)//2))
        self.frame = frame
        return frame

    def _draw_pet(self, frame, unit, center, height, enemy=False):
        if not unit:
            return
        from spine_renderer import animated_frame
        row = self.app.data.tables['Pet'][unit.pet.species]
        path = self.app.data.assets/'Sprite/Spine'/(row['filePath']+'.json')
        animation = 'stand'
        elapsed = time.monotonic()-self.animation_clock
        loop = True
        if self.visual_queue and self.visual_queue[0]['side'] == unit.side:
            animation = self.visual_queue[0]['animation']
            elapsed = time.monotonic()-self.visual_started
            loop = False
        if path.exists():
            image, offset, base_height = animated_frame(str(path), animation, elapsed, loop)
            ratio = height/base_height
            size = (max(1, round(image.width*ratio)), max(1, round(image.height*ratio)))
            image = image.resize(size, Image.Resampling.LANCZOS)
            if not enemy:
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                left = center[0]-(offset[0]*ratio+size[0])
            else:
                left = center[0]+offset[0]*ratio
            frame.alpha_composite(image, (round(left), round(center[1]+offset[1]*ratio)))
            return
        image = self.app.data.pet_image(unit.pet.species)
        if image is None:
            return
        ratio = height/max(1, image.height)
        image = image.resize((max(1, round(image.width*ratio)), height), Image.Resampling.LANCZOS)
        if not enemy:
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        frame.alpha_composite(image, (center[0]-image.width//2, center[1]-image.height//2))

    def _draw_bars(self, draw):
        for side, rects in self._hud_rects.items():
            for key, rect in rects.items():
                if key.endswith('/hp_LoadingBar'):
                    active = self.battle.enemy_active if side == 'enemy' else self.battle.player_active
                    if not active:
                        continue
                    color = (76, 200, 96, 255)
                    if active.hp/active.max_hp < .25:
                        color = (220, 64, 56, 255)
                    elif active.hp/active.max_hp < .55:
                        color = (238, 190, 70, 255)
                    self._bar(draw, rect, active.hp/active.max_hp, color)
                elif key.endswith('/energy_LoadingBar'):
                    active = self.battle.player_active
                    if active:
                        self._bar(draw, rect, active.energy/active.max_energy, (76, 150, 235, 255))

    def _draw_status(self, draw, unit, enemy):
        if not unit:
            return
        x = W*.52 if enemy else W*.04
        y = H*.09 if enemy else H*.70
        for index, buff in enumerate(unit.buffs[:6]):
            name = buff.name or buff.kind
            bad = buff.kind in ('poison', 'drain', 'leech', 'nightmare', 'doom',
                                'sleep', 'petrify', 'freeze', 'fear')
            color = (170, 45, 45, 230) if bad else (50, 130, 70, 230)
            draw.rounded_rectangle((x, y+index*22, x+94, y+index*22+19), 4, fill=color)
            self._label(draw, (x+47, y+index*22+9), f'{name}{buff.rounds}', 13, anchor='mm')

    def _draw_team(self, draw):
        for index, unit in enumerate(self.battle.enemy):
            x, y = W*.62+index*26, H*.045
            draw.ellipse((x, y, x+18, y+18), fill=(40, 40, 40, 220), outline=(230, 230, 230, 200))
            if not unit.alive:
                draw.line((x+4, y+4, x+14, y+14), fill=(220, 80, 80, 255), width=2)
                draw.line((x+14, y+4, x+4, y+14), fill=(220, 80, 80, 255), width=2)
        for index, unit in enumerate(self.battle.player):
            x, y = W*.04+index*26, H*.94
            draw.ellipse((x, y, x+18, y+18), fill=(40, 40, 40, 220), outline=(230, 230, 230, 200))
            if not unit.alive:
                draw.line((x+4, y+4, x+14, y+14), fill=(220, 80, 80, 255), width=2)
                draw.line((x+14, y+4, x+4, y+14), fill=(220, 80, 80, 255), width=2)

    # -- menus ---------------------------------------------------------------
    def _draw_main_menu(self, frame):
        layer, origin, hits = self._crop_layout(
            'BattleButtonMenuNode',
            visible={'runAway_Button': bool(self.battle.can_escape)},
            offset=(W*168/800, H*180/480))
        self._paste(frame, layer, origin, hits)

    def _skills(self):
        unit = self.battle.player_active
        if unit is None:
            return []
        return self.battle.available_skills(unit)[:4]

    def _draw_skill_menu(self, frame):
        entries = self._skills()
        text, visible = {}, {'catch_Button': bool(self.battle.can_catch)}
        for index in range(1, 5):
            key = f'skillMenu_{index}_Button'
            if index <= len(entries):
                row = entries[index-1]['row']
                visible[key] = True
                text[f'Node/battleSkillMenu_Panel/skill_Panel/{key}/name_Text'] = str(row.get('name', ''))
                text[f'Node/battleSkillMenu_Panel/skill_Panel/{key}/cost_BitmapFontLabel'] = str(row.get('energyCost', ''))
            else:
                visible[key] = False
        layer, origin, hits = self._crop_layout('BattleSkillMenuNode', text, visible,
                                                offset=(W*613/800, H*269/480))
        self._paste(frame, layer, origin, hits)
        draw = ImageDraw.Draw(frame, 'RGBA')
        for index in range(1, 5):
            key = f'skillMenu_{index}_Button'
            rect = self.hits.get(key)
            if not rect:
                continue
            if index <= len(entries):
                entry = entries[index-1]
                if not entry['usable']:
                    draw.rectangle(rect, fill=(0, 0, 0, 130))
                    if entry.get('cooldown'):
                        self._label(draw, ((rect[0]+rect[2])//2, (rect[1]+rect[3])//2),
                                    f'冷却{entry["cooldown"]}', 14, anchor='mm')
        self._label(draw, (30, H-118), '点击右侧技能；点击空白处返回', 15)

    def _battle_items(self, balls=False):
        rows = []
        for item_id, count in self.app.state.inventory.items():
            if count <= 0:
                continue
            row = self.app.data.tables['Item'].get(str(item_id))
            if not row:
                continue
            is_ball = str(item_id) in self.battle.catch_items
            if is_ball != balls:
                continue
            if not balls and int(row.get('useType', 0) or 0) not in (1, 2, 3):
                continue
            effect = self.app.data.tables.get('PetItem', {}).get(str(item_id))
            if not balls:
                if not effect or int(effect['type']) not in (1, 2, 3, 4):
                    continue
                if self.item_filter in (1, 2) and int(effect['type']) != 4:
                    pairs = str(effect['parameters']).split(',')
                    if str(self.item_filter) not in pairs[::2]:
                        continue
            rows.append((str(item_id), row, count))
        return rows

    def _draw_item_menu(self, frame, balls=False):
        all_rows = self._battle_items(balls)
        page = self.ball_page if balls else self.page
        rows = all_rows[page*4:(page+1)*4]
        text, visible = {}, {}
        for index in range(1, 5):
            key = f'itemMenu_{index}_Button'
            if index <= len(rows):
                item_id, row, count = rows[index-1]
                visible[key] = True
                text[f'Node/battleItemMenu_Panel/item_Panel/{key}/nameBg_Image/name_Text'] = str(row.get('name', item_id))
                text[f'Node/battleItemMenu_Panel/item_Panel/{key}/have_BitmapFontLabel'] = str(count)
            else:
                visible[key] = False
        layer, origin, hits = self._crop_layout('BattleItemMenuNode', text, visible,
                                                offset=(W*168/800, H*180/480))
        self._paste(frame, layer, origin, hits)
        draw = ImageDraw.Draw(frame, 'RGBA')
        if balls:
            self._label(draw, (30, H-118), '选择精灵球；点击空白处返回', 15)
        else:
            self._label(draw, (30, H-118), f'选择战斗道具  第{page+1}页（点击中央切换）', 15)
        if len(all_rows) > 4:
            cx, cy = W*168/800, H*(1-180/480)
            self.hits['item_center'] = (cx-38, cy-38, cx+38, cy+38)

    def _draw_pet_menu(self, frame, draw):
        frame.alpha_composite(Image.new('RGBA', (560, 300), (18, 22, 28, 235)), (40, 150))
        draw.rectangle((40, 150, 600, 450), outline=(220, 190, 120, 255), width=2)
        self._label(draw, (320, 165), '选择出战宠物', 20, (245, 215, 140, 255), 'ma')
        for index, unit in enumerate(self.battle.player):
            y = 195+index*40
            rect = (55, y, 585, y+34)
            fill = (52, 62, 74, 230) if unit.alive else (40, 40, 40, 180)
            if index == self.battle.player_index:
                fill = (74, 92, 60, 240)
            draw.rounded_rectangle(rect, 6, fill=fill)
            self.hits[f'pet_{index}'] = rect
            self._label(draw, (68, y+17), f'{unit.name}  Lv.{unit.pet.level}', 16, anchor='lm')
            self._label(draw, (420, y+17), f'HP {unit.hp}/{unit.max_hp}', 15, anchor='lm')
            self._label(draw, (525, y+17), '出战中' if index == self.battle.player_index else
                        ('可出战' if unit.alive else '已倒下'), 14, anchor='lm')
        self.hits['pet_back'] = (55, 420, 150, 444)
        self._label(draw, (102, 432), '返回', 15, anchor='mm')

    def _draw_confirm(self, frame, draw):
        frame.alpha_composite(Image.new('RGBA', (520, 220), (18, 22, 28, 240)), (252, 178))
        draw.rectangle((252, 178, 772, 398), outline=(220, 190, 120, 255), width=2)
        target = self.selected or {}
        row = self.app.data.tables['Item'].get(str(target.get('id', '')))
        name = row.get('name', '') if row else ''
        self._label(draw, (512, 215), f'使用 {name}？', 21, (245, 215, 140, 255), 'mm')
        if target.get('kind') == 'ball':
            self._label(draw, (512, 260), f'捕捉成功率约 {self.battle.capture_chance(target["id"])}%',
                        18, anchor='mm')
        self.hits['confirm_yes'] = (300, 330, 490, 376)
        self.hits['confirm_no'] = (534, 330, 724, 376)
        for key, label in (('confirm_yes', '确定'), ('confirm_no', '取消')):
            rect = self.hits[key]
            draw.rounded_rectangle(rect, 8, fill=(70, 92, 66, 240))
            self._label(draw, ((rect[0]+rect[2])//2, (rect[1]+rect[3])//2), label, 19, anchor='mm')

    def _draw_result(self, frame, draw):
        text = {'win': '战斗胜利', 'lose': '战斗失败', 'escape': '成功逃跑',
                'caught': '捕捉成功'}.get(self.battle.result, self.battle.result)
        frame.alpha_composite(Image.new('RGBA', (460, 190), (18, 22, 28, 245)), (282, 190))
        draw.rectangle((282, 190, 742, 380), outline=(230, 200, 120, 255), width=3)
        self._label(draw, (512, 240), text, 30, (248, 220, 140, 255), 'mm')
        lines = [m for m in self.battle.messages if '获得' in m or '捕捉' in m][-3:]
        for index, line in enumerate(lines):
            self._label(draw, (512, 285+index*24), line, 15, anchor='mm')
        self.hits['result_continue'] = (392, 335, 632, 374)
        draw.rounded_rectangle(self.hits['result_continue'], 8, fill=(72, 96, 68, 245))
        self._label(draw, (512, 354), '继续', 19, anchor='mm')

    def _draw_log(self, frame, draw):
        # Diagnostics live in the desktop status bar, not over the original HUD.
        return

    # -- input ---------------------------------------------------------------
    def click(self, x, y):
        self.advance_visual()
        if self.visual_queue:
            return None
        if self.info:
            self.info = ''
            return 'refresh'
        if self.battle.result:
            if self._inside(self.hits.get('result_continue'), x, y):
                return 'finish'
            return None
        for key, rect in sorted(self.hits.items(), key=lambda pair:
                                (pair[1][2]-pair[1][0])*(pair[1][3]-pair[1][1])):
            if self._inside(rect, x, y):
                return self._action(key)
        for key, rect in self.target_hits.items():
            if self._inside(rect, x, y):
                self.screen = 'pets' if self.battle.force_switch else (
                    'commands' if key == 'mineMenuPos_Panel' else 'skills')
                return 'refresh'
        if self.screen != 'main':
            self.screen = 'main'
            return 'refresh'
        return None

    @staticmethod
    def _inside(rect, x, y):
        return bool(rect) and rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]

    def _action(self, key):
        b = self.battle
        self.before_units = {'player': b.player_active, 'enemy': b.enemy_active}
        if key.startswith('skillInfo_Button_'):
            index = int(key.rsplit('_', 1)[1])-1
            entries = self._skills()
            if index < len(entries):
                row = entries[index]['row']
                self.info = str(row.get('des', row.get('name', '')))
        elif key.startswith('itemInfo_Button_'):
            rows = self._battle_items(balls=self.screen == 'balls')
            page = self.ball_page if self.screen == 'balls' else self.page
            index = page*4+int(key.rsplit('_', 1)[1])-1
            if index < len(rows):
                self.info = str(rows[index][1].get('des', rows[index][1].get('name', '')))
        elif key == 'energy_Button':
            self.item_filter, self.page, self.screen = 2, 0, 'items'
        elif key == 'bag_Button':
            self.item_filter, self.page, self.screen = None, 0, 'items'
        elif key == 'pet_Button':
            self.screen = 'pets'
        elif key == 'runAway_Button':
            if b.can_escape:
                b.choose_escape()
                return self._after_action()
            self.notice = '训练师对战中不能逃跑'
        elif key == 'hp_Button':
            self.item_filter, self.page, self.screen = 1, 0, 'items'
        elif key.startswith('skillMenu_'):
            b.choose_skill(int(key.split('_')[1]))
            self._after_action()
        elif key == 'attack_Button':
            b.choose_skill(0)
            self._after_action()
        elif key == 'catch_Button':
            self.screen = 'balls' if b.can_catch else 'items'
        elif key.startswith('itemMenu_'):
            rows = self._battle_items(balls=self.screen == 'balls')
            page = self.ball_page if self.screen == 'balls' else self.page
            rows = rows[page*4:(page+1)*4]
            index = int(key.split('_')[1])
            if index-1 < len(rows):
                item_id, row, count = rows[index-1]
                self.selected = {'id': item_id, 'kind': 'ball' if self.screen == 'balls' else 'item'}
                self.screen = 'confirm'
        elif key == 'item_center':
            if self.screen == 'balls':
                self.ball_page = (self.ball_page+1) % max(1, (len(self._battle_items(True))+3)//4)
            else:
                self.page = (self.page+1) % max(1, (len(self._battle_items(False))+3)//4)
        elif key == 'confirm_yes':
            item = (self.selected or {}).get('id')
            if item:
                if self.app.state.count(item) <= 0:
                    self.notice = '该道具数量不足。'
                    self.screen = 'main'
                    return 'refresh'
                events = b.choose_item(item)
                if any(event['type'] == 'catch_attempt' or
                       (event['type'] == 'item_used' and event.get('side') == 'player')
                       for event in events):
                    self.app.state.consume([item], [1])
            self.screen = 'main'
            self._after_action()
        elif key == 'confirm_no':
            self.screen = 'main'
        elif key.startswith('pet_'):
            if key == 'pet_back':
                self.screen = 'main'
            else:
                b.choose_switch(int(key.split('_')[1]))
                self.screen = 'main'
                self._after_action()
        return 'refresh'

    def _after_action(self):
        from spine_animation import duration
        from spine_renderer import load_skeleton
        self.visual_units = dict(self.before_units)
        self.visual_queue = []
        if not hasattr(self.app, 'data'):
            return self._complete_action()
        for event in self.battle.events:
            animation = {'attack': 'attack', 'skill': 'attack',
                         'damage': 'underattack', 'faint': 'dead'}.get(event['type'])
            side = event.get('side')
            if animation is None or side not in self.visual_units:
                continue
            unit = self.visual_units[side]
            if unit is None:
                continue
            row = self.app.data.tables['Pet'][unit.pet.species]
            path = self.app.data.assets/'Sprite/Spine'/(row['filePath']+'.json')
            if not path.exists():
                continue
            clip = load_skeleton(str(path)).get('animations', {}).get(animation)
            if clip is not None:
                self.visual_queue.append({'side': side, 'animation': animation,
                                          'duration': duration(clip)})
        if self.visual_queue:
            self.visual_started = time.monotonic()
            self.screen, self.notice = 'main', ''
            return 'refresh'
        return self._complete_action()

    def advance_visual(self):
        now = time.monotonic()
        while self.visual_queue and now-self.visual_started >= self.visual_queue[0]['duration']:
            self.visual_started += self.visual_queue.pop(0)['duration']
            if not self.visual_queue:
                self._complete_action()

    def _complete_action(self):
        b = self.battle
        if b.force_switch:
            self.screen = 'pets'
            self.notice = '请选择下一只宠物'
        elif b.result:
            self.screen = 'main'
            self.notice = ''
            if b.result in ('win', 'caught'):
                b.apply_rewards(self.app.state)
        else:
            self.screen = 'main'
            self.notice = ''
        if hasattr(self.app, 'battle_action_complete'):
            self.app.battle_action_complete()
        return 'refresh'
