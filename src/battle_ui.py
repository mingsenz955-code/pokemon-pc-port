"""Native battle presentation using the recovered Cocos Studio battle layouts.

The HUD is the original BattleMainUI; the command wheel is the original
BattleButtonMenuNode / BattleSkillMenuNode / BattleItemMenuNode. Dynamic text
and HP/energy fills are drawn over those layouts, and pet art comes from the
original Spine package rather than from screenshots.
"""
from __future__ import annotations

import math
import tkinter as tk

from PIL import Image, ImageDraw, ImageFont, ImageTk

W, H = 960, 576
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
        self.shop_hit = None
        self.item_filter = None
        self.info = ''
        # Replay action groups in order using authored Spine poses. The hit
        # phase and duration are still provisional, not native effect callbacks.
        self.anim = None
        self.anim_queue = []
        self.anim_frame = 0
        self.anim_idle = 0
        self.display_hp = {(u.side, u.pet.uid): u.hp for u in battle.player+battle.enemy}
        self.visual_hp = dict(self.display_hp)
        self._event_cursor = len(getattr(battle, 'events', []))
        self._event_batch = battle.events
        app.cocos_ui.render('BattleMainUI', (W, H), {})
        self.pet_positions = {side: tuple(app.cocos_ui.rects[node][:2]) for side, node in (
            ('player', 'minePetPos_Panel'), ('enemy', 'enemyPetPos_Panel'))}

    # -- animation -----------------------------------------------------------
    def advance(self, steps=1, *, seconds=None):
        # Keep the existing provisional action phases, but advance them in
        # elapsed time rather than one unit per potentially slow render.
        steps = max(0.0, float(steps) if seconds is None else float(seconds)*25)
        self.anim_idle += steps
        remaining = steps
        while self.anim and remaining > 0:
            amount = min(remaining, self.anim['duration']-self.anim['age'])
            self.anim['age'] += amount
            remaining -= amount
            if self.anim['age'] >= self.anim['duration']/2:
                for event in self.anim.get('damages', []):
                    if event.get('uid'):
                        self.visual_hp[(event['side'], event['uid'])] = event['hp']
            if self.anim['age'] >= self.anim['duration']:
                self.anim = self.anim_queue.pop(0) if self.anim_queue else None
            self.frame = None
            self._signature = None
        # Smoothly drain/fill the bars instead of snapping to the new value.
        for side, unit in (('player', self.battle.player_active),
                           ('enemy', self.battle.enemy_active)):
            if not unit:
                continue
            key = (side, unit.pet.uid)
            target = int(self.visual_hp.get(key, unit.hp) if self.anim else unit.hp)
            current = self.display_hp.get(key)
            if current is None or current == target:
                self.display_hp[key] = target
                continue
            delta = target-current
            step = max(1, abs(delta)//8+1)
            self.display_hp[key] = current + (step if delta > 0 else -step)
            self.frame = None
            self._signature = None

    def _capture_events(self):
        events = getattr(self.battle, 'events', [])
        # Battle replaces the per-round list. Its length is not a global
        # cursor: equal-length consecutive rounds must both be replayed.
        cursor = getattr(self, '_event_cursor', 0) if events is getattr(self, '_event_batch', None) else 0
        fresh = events[cursor:]
        self._event_batch = events
        self._event_cursor = len(events)
        if not fresh:
            return
        current = None
        for event in fresh:
            kind = event.get('type')
            if kind in ('attack', 'skill'):
                current = {'side': event.get('side', 'player'), 'target': '', 'kind': kind,
                           'source_uid': event.get('uid'), 'amount': 0, 'crit': False,
                           'age': 0, 'duration': 26, 'damages': []}
                self.anim_queue.append(current)
            elif kind == 'damage':
                if current is None:
                    current = {'side': '', 'target': event['side'], 'kind': 'damage',
                               'amount': 0, 'crit': False, 'age': 0, 'duration': 26, 'damages': []}
                    self.anim_queue.append(current)
                current['target'] = event['side']
                current['target_uid'] = event.get('uid')
                current['amount'] += int(event.get('amount', 0))
                current['crit'] |= bool(event.get('crit'))
                current['damages'].append(event)
        if self.anim is None and self.anim_queue:
            self.anim = self.anim_queue.pop(0)
        self._signature = None

    def _animation_offsets(self):
        # Pet motion comes from the authored Spine timelines.
        return (0, 0), (0, 0), 0.0

    def presentation_unit(self, enemy=False):
        side = 'enemy' if enemy else 'player'
        team = self.battle.enemy if enemy else self.battle.player
        if self.anim:
            uid = (self.anim.get('source_uid') if self.anim['side'] == side else
                   self.anim.get('target_uid') if self.anim['target'] == side else None)
            unit = next((u for u in team if u.pet.uid == uid), None)
            if unit:
                return unit
        return self.battle.enemy_active if enemy else self.battle.player_active

    # -- HUD ----------------------------------------------------------------
    def _hud_layer(self, enemy):
        side = 'enemy' if enemy else 'mine'
        active = self.presentation_unit(enemy)
        if not active:
            return None
        petrow = self.app.data.tables['Pet'][active.pet.species]
        shown_hp = self.display_hp.get(('enemy' if enemy else 'player', active.pet.uid), active.hp)
        text = {
            f'{side}_name_Text': active.name,
            'lv_BitmapFontLabel': str(active.pet.level),
            'hp_BitmapFontLabel': f'{shown_hp}/{active.max_hp}',
            f'{side}FightPercent_BitmapFontLabel': f'{shown_hp*100//active.max_hp}%',
        }
        if not enemy:
            text['energy_BitmapFontLabel'] = f'{active.energy}/{active.max_energy}'
        visible = {'enemy_Panel': enemy, 'mine_Panel': not enemy,
                   'enemyCount_Panel': False, 'catched_Sprite': False,
                   'finded_Sprite': False, 'chat_Panel': False,
                   'leftButtons_Panel': True}
        relation = int(petrow.get('restraint', 3) or 3)
        kind = {1: 'life', 2: 'energy', 3: 'power', 4: 'defence',
                5: 'speed', 6: 'all'}.get(relation, 'power')
        resources = {'kindIcon_Sprite': f'UI/pet_kind_{kind}.png'}
        layer = self.app.cocos_ui.render('BattleMainUI', (W, H), text, visible, resources)
        if 'battleShop_Button' in self.app.cocos_ui.buttons:
            self.shop_hit = self.app.cocos_ui.buttons['battleShop_Button']
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
        signature = (self.screen, self.page, self.ball_page, self.notice, self.info,
                     int(self.anim_idle*12/25),
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
        source_offset, target_offset, flash = self._animation_offsets()
        if self.anim:
            enemy_offset = source_offset if self.anim['side'] == 'enemy' else target_offset
            player_offset = source_offset if self.anim['side'] == 'player' else target_offset
        else:
            enemy_offset, player_offset = (0, 0), (0, 0)
        self._draw_pet(frame, self.presentation_unit(True),
                       tuple(round(v)+d for v, d in zip(self.pet_positions['enemy'], enemy_offset)),
                       235, True, flash if self.anim and self.anim['target'] == 'enemy' else 0)
        self._draw_pet(frame, self.presentation_unit(False),
                       tuple(round(v)+d for v, d in zip(self.pet_positions['player'], player_offset)),
                       250, False, flash if self.anim and self.anim['target'] == 'player' else 0)
        for layer in (self._hud_layer(True), self._hud_layer(False)):
            if layer:
                frame.alpha_composite(layer)
        draw = ImageDraw.Draw(frame, 'RGBA')
        self._draw_bars(draw)
        self._draw_status(draw, self.presentation_unit(True), True)
        self._draw_status(draw, self.presentation_unit(False), False)
        self._draw_team(draw)
        self._draw_damage(draw)
        self.hits = {}
        if self.shop_hit:
            self.hits['battleShop_Button'] = self.shop_hit
        if self.battle.result and not self.anim:
            self._draw_result(frame, draw)
        elif self.anim or self.screen == 'main':
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

    def _draw_pet(self, frame, unit, center, height, enemy=False, flash=0.0):
        if not unit:
            return
        setup = self.app.data.pet_image(unit.pet.species)
        if setup is None:
            return
        clip, age, loop = 'stand', self.anim_idle, True
        side = 'enemy' if enemy else 'player'
        if self.anim and self.anim['side'] == side:
            clip, age, loop = 'attack', self.anim['age'], False
        elif self.anim and self.anim['target'] == side and self.anim['age'] >= self.anim['duration']/2:
            clip, age, loop = 'underattack', self.anim['age']-self.anim['duration']/2, False
        image = self.app.data.pet_frame(unit.pet.species, clip, int(age*12/25), loop)
        if image is None:
            image = setup
        ratio = height/max(1, setup.height)
        origin = image.info.get('origin', (image.width/2, image.height))
        origin = (origin[0]*ratio, origin[1]*ratio)
        image = image.resize((max(1, round(image.width*ratio)), max(1, round(image.height*ratio))), Image.Resampling.LANCZOS)
        if not enemy:
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            origin = (image.width-origin[0], origin[1])
        if flash:
            overlay = Image.new('RGBA', image.size, (255, 48, 32, 255))
            image = Image.blend(image, overlay, min(.55, .55*flash))
        frame.alpha_composite(image, (round(center[0]-origin[0]), round(center[1]-origin[1])))

    def _draw_damage(self, draw):
        if not self.anim or self.anim['amount'] <= 0:
            return
        half = self.anim['duration']/2
        if self.anim['age'] < half:
            return
        phase = min(1.0, (self.anim['age']-half)/max(1, half))
        side = self.anim['target']
        x = round(self.pet_positions[side][0])
        y = round(self.pet_positions[side][1])-260
        y -= round(34*phase)
        text = f'-{self.anim["amount"]}'
        if self.anim['crit']:
            text += ' 暴击!'
        self._label(draw, (x, y), text, 28 if self.anim['crit'] else 24,
                    (255, 236, 120, 255) if self.anim['crit'] else (255, 92, 72, 255), 'mm')

    def _draw_bars(self, draw):
        for side, rects in self._hud_rects.items():
            for key, rect in rects.items():
                if key.endswith('/hp_LoadingBar'):
                    active = self.presentation_unit(side == 'enemy')
                    if not active:
                        continue
                    key_hp = ('enemy' if side == 'enemy' else 'player', active.pet.uid)
                    shown = self.display_hp.get(key_hp, active.hp)
                    color = (76, 200, 96, 255)
                    if active.hp/active.max_hp < .25:
                        color = (220, 64, 56, 255)
                    elif active.hp/active.max_hp < .55:
                        color = (238, 190, 70, 255)
                    self._bar(draw, rect, shown/active.max_hp, color)
                elif key.endswith('/energy_LoadingBar'):
                    active = self.presentation_unit(False)
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
            if not balls and int(row.get('useType', 0) or 0) not in (1, 3):
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
        if len(all_rows) > 4:
            cx, cy = W*168/800, H*(1-180/480)
            self.hits['item_center'] = (cx-38, cy-38, cx+38, cy+38)

    def _draw_pet_menu(self, frame, draw):
        ui = self.app.cocos_ui
        layer = ui.render('PetSelectUI', (W, H), visible={'close_Button': not self.battle.force_switch})
        rect = ui.rects['pet_ListView']
        self.hits['pet_back'] = ui.buttons.get('close_Button', (-1, -1, -1, -1))
        left, top, right, bottom = [round(v) for v in rect]
        viewport = Image.new('RGBA', (right-left, bottom-top))
        scale = W/800
        row_height = 74*scale
        self.pet_scroll = min(getattr(self, 'pet_scroll', 0), max(0, len(self.battle.player)*row_height-viewport.height))
        for index, unit in enumerate(self.battle.player):
            y = index*row_height-self.pet_scroll
            if y+row_height <= 0 or y >= viewport.height:
                continue
            row = self.app.data.tables['Pet'][unit.pet.species]
            kind = self.app.data.tables['PetKindEnum'][str(row['kind'])]['iconTexture']
            art = ui.render('PetSelectItemUI', (round(309*scale), round(row_height)),
                {'name_Text': unit.name, 'lv_BitmapFontLabel': str(unit.pet.level),
                 'hpHave_BitmapFontLabel': str(unit.hp), 'hpMax_BitmapFontLabel': str(unit.max_hp),
                 'enHave_BitmapFontLabel': str(unit.energy), 'enMax_BitmapFontLabel': str(unit.max_energy),
                 'friendly_BitmapFontLabel': str(unit.pet.friendly)},
                {'selected_Image': index == self.battle.player_index},
                {'kind_Image': 'UI/'+kind})
            if not unit.alive:
                alpha = art.getchannel('A')
                art = art.convert('LA').convert('RGBA')
                art.putalpha(alpha)
            viewport.alpha_composite(art, (0, round(y)))
            self.hits[f'pet_{index}'] = (left, max(top, top+y), right, min(bottom, top+y+row_height))
        layer.alpha_composite(viewport, (left, top))
        frame.alpha_composite(layer)

    def wheel(self, delta):
        if self.screen == 'pets':
            self.pet_scroll = max(0, getattr(self, 'pet_scroll', 0)-delta*74*(W/800))
            self.frame = None

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
        if self.anim:
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
        if self.screen == 'pets' and self.battle.force_switch:
            return None
        if self.screen != 'main':
            self.screen = 'main'
            return 'refresh'
        return None

    @staticmethod
    def _inside(rect, x, y):
        return bool(rect) and rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]

    def _action(self, key):
        b = self.battle
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
        elif key == 'battleShop_Button':
            self.battle_shop()
        elif key.startswith('itemMenu_'):
            rows = self._battle_items(balls=self.screen == 'balls')
            page = self.ball_page if self.screen == 'balls' else self.page
            rows = rows[page*4:(page+1)*4]
            index = int(key.split('_')[1])
            if index-1 < len(rows):
                item_id, row, count = rows[index-1]
                self.selected = {'id': item_id, 'kind': 'ball' if self.screen == 'balls' else 'item'}
                return self._action('confirm_yes')
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

    def battle_shop(self):
        """Original BattleShopUI: real BattleShop rows, no simulated payment."""
        if getattr(self, 'shop_window', None) is not None:
            try:
                self.shop_window.lift()
                return
            except tk.TclError:
                self.shop_window = None
        self.shop_window = tk.Toplevel(self.app.root)
        win = self.shop_window
        win.title('战斗商店 · 原版 BattleShopUI')
        win.transient(self.app.root)
        win.resizable(False, False)
        try:
            layer = self.app.cocos_ui.render('BattleShopUI', (800, 480), {})
            photo = ImageTk.PhotoImage(layer)
            art = tk.Label(win, image=photo, bg='#101418')
            art.image = photo
            art.pack()
        except (FileNotFoundError, ValueError, KeyError, OSError):
            tk.Label(win, text='BattleShopUI 原版布局读取失败。',
                     bg='#202b30', fg='#ffb0a0').pack(padx=20, pady=20)
        info = tk.StringVar(value='战斗商店：购买后道具进入背包，战斗继续。')
        body = tk.Frame(win, bg='#202b30')
        body.pack(fill='both', expand=True, padx=12, pady=8)
        tk.Label(body, textvariable=info, bg='#202b30', fg='#f2e7cf',
                 font=('Microsoft YaHei UI', 10), anchor='w').pack(fill='x')
        rows = sorted(self.app.data.tables['BattleShop'].items(),
                      key=lambda pair: int(pair[0]))
        goods_rect = (self.app.cocos_ui.hits.get('goods_ListView')
                      or self.app.cocos_ui.rects.get('goods_ListView'))
        list_frame = tk.Frame(win, bg='#202b30', highlightthickness=0)
        if goods_rect:
            list_frame.place(x=goods_rect[0], y=goods_rect[1],
                             width=max(100, goods_rect[2]-goods_rect[0]),
                             height=max(80, goods_rect[3]-goods_rect[1]))
            list_frame.lift()
        else:
            list_frame.pack(fill='both', expand=True, padx=12, pady=8)
        box = tk.Listbox(list_frame, width=82, height=9, font=('Microsoft YaHei UI', 9),
                         bg='#182125', fg='#e8d8b8', selectbackground='#49606a')
        bar = tk.Scrollbar(list_frame, command=box.yview)
        box.configure(yscrollcommand=bar.set)
        box.pack(side='left', fill='both', expand=True)
        bar.pack(side='right', fill='y')
        for key, row in rows:
            currency = self.app.data.tables['Money'].get(
                str(row['moneyType']), {}).get('name', row['moneyType'])
            box.insert('end', f'{row["name"]}  {row["price"]} {currency}  — {row.get("des", "")}')

        def buy():
            if not box.curselection():
                info.set('请先选择商品。')
                return
            key, row = rows[box.curselection()[0]]
            try:
                self.app.state.buy('BattleShop', key)
            except (ValueError, KeyError) as error:
                info.set(str(error))
                return
            info.set(f'购买成功：{row["name"]} · 背包数量 '
                     f'{self.app.state.count(row["goodsKid"])}')

        def close():
            try:
                win.destroy()
            except tk.TclError:
                pass
            self.shop_window = None

        tk.Button(body, text='购买', bg='#5b7c52', fg='white',
                  command=buy).pack(side='left', padx=6, anchor='n')
        tk.Button(body, text='关闭', command=close).pack(side='left', padx=6, anchor='n')
        self.shop_box = box
        self.shop_actions = {'buy': buy, 'close': close}
        win.protocol('WM_DELETE_WINDOW', close)
        win.bind('<Escape>', lambda _: close())

    def _after_action(self):
        b = self.battle
        self._capture_events()
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
