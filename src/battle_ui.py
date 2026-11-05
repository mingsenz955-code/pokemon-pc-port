"""Native battle presentation using the recovered Cocos Studio battle layouts.

The HUD is the original BattleMainUI; the command wheel is the original
BattleButtonMenuNode / BattleSkillMenuNode / BattleItemMenuNode. Dynamic text
and HP/energy fills are drawn over those layouts, and pet art comes from the
original Spine package rather than from screenshots.
"""
from __future__ import annotations

import math
from collections import OrderedDict
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFont
from armature_composite import composite
from pet_appearance import quality_color, pet_flash

W, H = 960, 576
FONT = 'C:/Windows/Fonts/msyh.ttc'


@lru_cache(maxsize=64)
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
    def __init__(self, app, battle, *, opening=False):
        self.app = app
        self.battle = battle
        from battle_effects import BattleEffects, EffectAudio
        self.effects = BattleEffects(app.data)
        self.effect_audio = getattr(app, 'audio', None) or EffectAudio(app.data)
        self.pet_bones = {}
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
        self._hud_cache = OrderedDict()
        self._pose_cache = OrderedDict()
        self._buff_icons = {}
        self._background_cache = {}
        self.result_page = 'outcome'
        self.result_age = 0.0
        self.levelup_entries = None
        self.levelup_index = 0
        self.levelup_age = 0.0
        # Replay authored action callbacks. Unsupported plans retain the
        # explicitly provisional 26-tick fallback.
        self.anim = None
        self.anim_queue = []
        self.anim_frame = 0
        self.anim_idle = 0
        self.opening_frame = 0.0 if opening else None
        self._entry_voice_played = False
        self._enemy_entry_voice_played = False
        self.opening_transition = (app.cocos_ui.layout('BattleStartEffectUI')['action']['duration']
                                   if opening else 0)
        self.display_hp = {(u.side, u.pet.uid): u.hp for u in battle.player+battle.enemy}
        self.visual_hp = dict(self.display_hp)
        self._event_cursor = len(getattr(battle, 'events', []))
        self._event_batch = battle.events
        app.cocos_ui.render('BattleMainUI', (W, H), {})
        self.pet_positions = {side: tuple(app.cocos_ui.rects[node][:2]) for side, node in (
            ('player', 'minePetPos_Panel'), ('enemy', 'enemyPetPos_Panel'))}

    # -- animation -----------------------------------------------------------
    def advance(self, steps=1, *, seconds=None):
        # Use elapsed time so slow renders still cross every authored callback.
        steps = max(0.0, float(steps) if seconds is None else float(seconds)*25)
        if self.opening_frame is not None:
            previous = self.opening_frame
            # The first tick after a battle is created can carry the long map
            # frame that built the battle.  Do not let that one delta skip the
            # whole authored BattleStartEffectUI (60 frames) before it is seen.
            if previous == 0 and steps > 1:
                steps = 1
            self.opening_frame += steps*60/25
            voice_frame = self.opening_transition+3
            if previous <= voice_frame < self.opening_frame:
                self.effect_audio.play('5023')
            # Enemy and player cries are separate MCI aliases so the second
            # pet does not cut the first one.  Most rows have no Sound entry;
            # those stay silent instead of borrowing an unrelated asset.
            if not self._enemy_entry_voice_played and self.opening_frame >= self.opening_transition+self._entry_plan('enemy')['reveal']:
                self._enemy_entry_voice_played = True
                unit = getattr(self.battle, 'enemy_active', None)
                if unit is not None:
                    row = self.app.data.tables['Pet'].get(unit.pet.species, {})
                    sound = str(row.get('wowSound', '0'))
                    if sound not in ('', '0') and sound in self.app.data.tables.get('Sound', {}):
                        second = getattr(self.effect_audio, 'effect2', None)
                        (second or self.effect_audio.play)(sound)
            if not self._entry_voice_played and self.opening_frame >= self.opening_transition+self._entry_plan('player')['reveal']:
                self._entry_voice_played = True
                unit = getattr(self.battle, 'player_active', None)
                if unit is not None:
                    row = self.app.data.tables['Pet'].get(unit.pet.species, {})
                    sound = str(row.get('wowSound', '0'))
                    if sound not in ('', '0') and sound in self.app.data.tables.get('Sound', {}):
                        self.effect_audio.play(sound)
            if self.opening_frame >= self.opening_transition+max(self._entry_plan(s)['duration'] for s in self._entry_ball_sides()):
                self.opening_frame = None
            self.frame = None
        self.anim_idle += steps
        if self.battle.result and not self.anim and self.opening_frame is None and self.result_page == 'outcome':
            if self._levelup_active():
                # PetLevelUpUILayer is shown before BattleCalculationUILayer;
                # confirm advances through every leveled pet.
                self.levelup_age += steps*60/25
            else:
                # PetCatchedEffectUI (200 frames) and ChallengeResultUI (170)
                # are authored timelines; keep them moving while the result page
                # waits for the player's confirmation tap.
                self.result_age += steps*60/25
            self.frame = None
            self._signature = None
        remaining = steps
        while self.anim and remaining > 0:
            if not self.anim.get('started'):
                self.anim['started'] = True
                if self.anim.get('cast_sound') and hasattr(self.app, 'root'):
                    self.effect_audio.play(self.anim['cast_sound'])
            amount = min(remaining, self.anim['duration']-self.anim['age'])
            self.anim['age'] += amount
            remaining -= amount
            plan = self.anim.get('effect')
            if plan and hasattr(self.app, 'root'):
                played = self.anim.setdefault('played_events', set())
                for index, (when, name) in enumerate(plan['events']):
                    if self.anim['age'] >= when and index not in played and name == 'sound':
                        self.effect_audio.play(plan['sound'])
                        played.add(index)
                # Two X armatures author a sound filename but have no sound
                # callback frame; the native loader still starts it with the
                # effect, so play it once at animation start.
                if plan.get('sound') and not any(name == 'sound' for _, name in plan['events']):
                    if 'start_sound' not in played:
                        self.effect_audio.play(plan['sound'])
                        played.add('start_sound')
            if self.anim.get('kind') == 'capture':
                played = self.anim.setdefault('capture_sounds',set())
                for index,(when,name) in enumerate(self.anim['capture_plan']['events']):
                    sound = {'cici':'6029','cici2':'6030','failedsound':'6030'}.get(name)
                    if sound and self.anim['age']*60/25 >= when and index not in played:
                        self.effect_audio.play(sound)
                        played.add(index)
            for event in self.anim.get('damages', []):
                if not event.get('presented') and self.anim['age'] >= event['when']:
                    event['presented'] = True
                    self.anim['impact'] = event
                    if event.get('uid') and 'hp' in event:
                        self.visual_hp[(event['side'], event['uid'])] = event['hp']
            if self.anim['age'] >= self.anim['duration']:
                if self.anim.get('response_sound'):
                    self.effect_audio.play(self.anim['response_sound'])
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
            if kind == 'catch_attempt':
                success = any(e.get('type') == 'caught' for e in fresh)
                # Both native outcomes begin at Animation7 and follow
                # their distinct ELF catch_*_seq completion chains.
                plan = self._capture_plan(success)
                name = plan['segments'][0][0]
                frames = plan['response']
                current = {'side': 'enemy', 'target': 'enemy', 'kind': 'capture',
                           'source_uid': self.battle.enemy_active.pet.uid,
                           'amount': 0, 'crit': False, 'age': 0,
                           'duration': frames*25/60, 'damages': [],
                           'capture_clip': name, 'capture_success': success, 'capture_plan': plan}
                self.anim_queue.append(current)
                if success:
                    species = next((str(e.get('name')) for e in fresh
                                    if e.get('type') == 'caught' and e.get('name')), None)
                    if species:
                        row = self.app.data.tables['Pet'].get(species, {})
                        sound = str(row.get('wowSound', '0'))
                        if sound not in ('', '0') and sound in self.app.data.tables.get('Sound', {}):
                            current['response_sound'] = sound
            elif kind in ('attack', 'skill'):
                current = {'side': event.get('side', 'player'), 'target': '', 'kind': kind,
                           'source_uid': event.get('uid'), 'amount': 0, 'crit': False,
                           'idle': event.get('skill_id') == '300071',
                           'age': 0, 'duration': 26, 'damages': []}
                plan = self.effects.plan(event.get('skill_id', '300056'), current['side'])
                if plan:
                    current['effect'] = plan
                    current['duration'] = plan['duration']
                    current['hit_at'] = plan['hit'] if plan['hit'] is not None else plan['duration']
                skill_row = self.app.data.tables.get('Skill', {}).get(
                    str(event.get('skill_id', '300056')), {})
                current['shake'] = int(skill_row.get('shake', 0) or 0)
                # Skill.sound is the authored cast/hit SFX; SkillEffect.sound is
                # the armature's own filename callback.  Both are original data.
                sound = str(skill_row.get('sound', '0'))
                if sound not in ('', '0') and sound in self.app.data.tables.get('Sound', {}):
                    current['cast_sound'] = sound
                self.anim_queue.append(current)
            elif kind == 'item_used':
                effect = self.app.data.tables.get('PetItem', {}).get(str(event.get('id')), {})
                sound = str(effect.get('soundId', '0'))
                plan = self.effects.plan_effect(str(effect.get('effectId', '0')))
                if plan:
                    current = {'side': event.get('side', 'player'),
                               'target': event.get('side', 'player'), 'kind': 'item',
                               'source_uid': self.battle.player_active.pet.uid,
                               'amount': 0, 'crit': False, 'age': 0,
                               'duration': plan['duration'],
                               'hit_at': plan['hit'] if plan['hit'] is not None else plan['duration'],
                               'damages': [], 'effect': plan, 'shake': 0,
                               'cast_sound': sound if sound not in ('', '0') else None}
                    self.anim_queue.append(current)
            elif kind in ('escape', 'enemy_escape'):
                side = 'player' if kind == 'escape' else 'enemy'
                unit = self.battle.player_active if side == 'player' else self.battle.enemy_active
                if unit is not None:
                    self.anim_queue.append({
                        'side': side, 'target': side, 'source_uid': unit.pet.uid,
                        'kind': 'escape', 'amount': 0, 'crit': False,
                        'age': 0, 'duration': 10, 'damages': []})
            elif kind == 'escape_failed':
                unit = self.battle.player_active
                if unit is not None:
                    self.anim_queue.append({
                        'side': 'player', 'target': 'player',
                        'source_uid': unit.pet.uid, 'kind': 'escape_failed',
                        'amount': 0, 'crit': False, 'age': 0,
                        'duration': 10, 'damages': []})
            elif kind == 'switch':
                unit = next((u for u in self.battle.player+self.battle.enemy
                             if u.pet.uid == event.get('uid')), None)
                if unit is not None:
                    self.anim_queue.append({
                        'side': event.get('side', unit.side), 'target': '',
                        'source_uid': unit.pet.uid, 'kind': 'switch',
                        'amount': 0, 'crit': False, 'age': 0,
                        'duration': self._entry_plan(event.get('side', unit.side))['duration']*25/60, 'damages': []})
            elif kind == 'faint':
                unit = next((u for u in self.battle.player+self.battle.enemy
                             if u.pet.uid == event.get('uid')), None)
                if unit is not None:
                    self.anim_queue.append({
                        'side': event.get('side', unit.side), 'target': '',
                        'source_uid': unit.pet.uid, 'kind': 'faint',
                        'amount': 0, 'crit': False, 'age': 0,
                        'duration': 30, 'damages': []})
            elif kind in ('damage', 'heal'):
                if current is None:
                    current = {'side': '', 'target': event['side'], 'kind': 'damage',
                               'amount': 0, 'crit': False, 'age': 0, 'duration': 26, 'damages': []}
                    self.anim_queue.append(current)
                current['target'] = event['side']
                current['target_uid'] = event.get('uid')
                current['amount'] += int(event.get('amount', 0))
                current['crit'] |= bool(event.get('crit'))
                hits = current.get('effect', {}).get('hits', ())
                when = (hits[min(int(event.get('hit_index', 0)), len(hits)-1)] if hits else
                        current.get('hit_at', current['duration']/2))
                current['damages'].append({**event, 'when': when})
        if self.anim is None and self.anim_queue:
            self.anim = self.anim_queue.pop(0)
        self._signature = None

    def _animation_offsets(self):
        # Pet motion comes from the authored Spine timelines.  Escape is a
        # controller action rather than a skill armature: the fleeing pet runs
        # out of the authored pet anchor before the result layer appears.
        if self.anim and self.anim.get('kind') in ('escape', 'escape_failed'):
            # PetController::escape @ 0x2cff64 has two CardinalSplineBy
            # actions: the successful run is 7 points ending +400, while a
            # failed attempt hops through 5 points and returns to its anchor.
            # Both use 0.4s and tension 0.
            age = max(0.0, self.anim['age'])
            t = min(1.0, age/(25*.4))
            if self.anim['kind'] == 'escape_failed':
                points = ((0, 0), (-150, 85), (-70, 195),
                          (70, 135), (0, 0))
            else:
                points = ((0, 0), (-215, 80), (-250, 205), (-100, 265),
                          (75, 250), (235, 150), (400, 0))
            segments = len(points)-1
            scaled = min(segments-1e-9, t*segments)
            index = int(scaled)
            local = scaled-index
            p0 = points[max(0, index-1)]
            p1 = points[index]
            p2 = points[index+1]
            p3 = points[min(segments, index+2)]
            # cocos2d::ccCardinalSplineAt with tension 0.
            x = .5*((2*p1[0])+(-p0[0]+p2[0])*local
                    +(2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*local*local
                    +(-p0[0]+3*p1[0]-3*p2[0]+p3[0])*local**3)
            y = .5*((2*p1[1])+(-p0[1]+p2[1])*local
                    +(2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*local*local
                    +(-p0[1]+3*p1[1]-3*p2[1]+p3[1])*local**3)
            ratio = W/800
            side = self.anim.get('side')
            mirror = self.anim['kind'] == 'escape' and side == 'player'
            offset = (round((-x if mirror else x)*ratio),
                      round(-y*ratio))
            # The first slot is always the animated side's node; render()
            # maps it to the fleeing player or enemy respectively.
            return offset, (0, 0), 0.0
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
        cache_key = (enemy, active.pet.uid, active.pet.level, active.name, active.max_hp,
                     active.max_energy, shown_hp, active.energy, getattr(active.pet, 'quality', 1))
        cached = self._hud_cache.get(cache_key)
        if cached is not None:
            layer, targets, rects, shop = cached
            self.target_hits.update(targets)
            self._hud_rects[side] = rects
            self.shop_hit = shop
            self._hud_cache.move_to_end(cache_key)
            return layer
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
        layer = self.app.cocos_ui.render('BattleMainUI', (W, H), text, visible, resources,
                                       colors={f'{side}_name_Text': quality_color(active.pet)})
        if 'battleShop_Button' in self.app.cocos_ui.buttons:
            self.shop_hit = self.app.cocos_ui.buttons['battleShop_Button']
        for name in ('mineMenuPos_Panel', 'enemyMenuPos_Panel'):
            if name in self.app.cocos_ui.rects:
                self.target_hits[name] = self.app.cocos_ui.rects[name]
        self._hud_rects[side] = {
            key: value for key, value in self.app.cocos_ui.rects.items()
            if key.endswith('/hp_LoadingBar') or key.endswith('/energy_LoadingBar')}
        targets = dict(self.target_hits)
        self._hud_cache[cache_key] = (layer, targets, self._hud_rects[side], self.shop_hit)
        if len(self._hud_cache) > 8:
            self._hud_cache.popitem(last=False)
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
    def battle_land(self):
        land = str(getattr(getattr(self.app, 'map', None), 'info', {}).get('landType', '1'))
        active = self.battle.player_active
        if active is not None and getattr(active, 'terrain_override', None):
            land = active.terrain_override
        return land

    def _shake_offset(self):
        """Skill.shake=1 (Ground Wrath) shakes the battlefield, not the HUD."""
        anim = self.anim
        if not anim or not anim.get('shake'):
            return 0, 0
        hit = float(anim.get('hit_at') or 0)
        age = float(anim.get('age') or 0)
        if age < hit or age > hit+14:
            return 0, 0
        phase = age-hit+0.5
        return round(math.sin(phase*1.7)*7), round(math.cos(phase*2.3)*4)

    def render(self):
        signature = (self.screen, self.page, self.ball_page, self.notice, self.info, self.result_page, getattr(self, 'result_index', 0),
                     int(self.anim_idle*30/25),
                     int(self.anim['age']*60/25) if self.anim else -1,
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
        land = self.battle_land()
        background = None
        for candidate in (land, '1', '2'):
            try:
                background = self.app.data.image(f'res/UI/image_battleground{candidate}.png')
                break
            except (KeyError, OSError):
                continue
        if background is None:
            background = getattr(self.app, 'background', None)
        if land not in self._background_cache:
            self._background_cache[land] = cover(background, (W, H))
        shake_x, shake_y = self._shake_offset()
        if shake_x or shake_y:
            frame.alpha_composite(ImageChops.offset(
                self._background_cache[land], shake_x, shake_y))
        else:
            frame.alpha_composite(self._background_cache[land])
        if self.opening_frame is not None and self.opening_frame < self.opening_transition:
            frame.alpha_composite(self.app.cocos_ui.render(
                'BattleStartEffectUI', (W, H), timeline_frame=int(self.opening_frame)))
            self.hits = {}
            self.frame = frame
            return frame
        if self.battle.result and not self.anim and self.opening_frame is None and self.result_page == 'outcome' and self._levelup_active():
            # PetLevelUpUI is a full-screen settlement layer: do not leave
            # the battle pets/HUD visible behind its own pet portrait.
            self._draw_levelup(frame)
            self.frame = frame
            return frame
        source_offset, target_offset, flash = self._animation_offsets()
        if self.anim:
            enemy_offset = source_offset if self.anim['side'] == 'enemy' else target_offset
            player_offset = source_offset if self.anim['side'] == 'player' else target_offset
        else:
            enemy_offset, player_offset = (0, 0), (0, 0)
        pets_layer = Image.new('RGBA', frame.size)
        self._draw_pet(pets_layer, self.presentation_unit(True),
                       tuple(round(v)+d+s for v, d, s in
                             zip(self.pet_positions['enemy'], enemy_offset,
                                 (shake_x, shake_y))),
                       235, True, flash if self.anim and self.anim['target'] == 'enemy' else 0)
        self._draw_pet(pets_layer, self.presentation_unit(False),
                       tuple(round(v)+d+s for v, d, s in
                             zip(self.pet_positions['player'], player_offset,
                                 (shake_x, shake_y))),
                       250, False, flash if self.anim and self.anim['target'] == 'player' else 0)
        self.effects.draw(frame, self, rear=True)
        frame.alpha_composite(pets_layer)
        if self.opening_frame is not None:
            age = self.opening_frame-self.opening_transition
            # The original PetController opens a Skill/kaichong ball before
            # the appearance flash. Replay the native five-clip sequence;
            # its Animation3 'out' event releases the pet.
            self._draw_entry_ball(frame, age)
            for side in self._entry_ball_sides():
                self._draw_appearance_flash(frame, side, age)
        if self.anim and self.anim.get('kind') == 'switch':
            age = self.anim['age']*60/25
            self._draw_entry_ball(frame, age, (self.anim['side'],))
            self._draw_appearance_flash(frame, self.anim['side'], age)
        self.effects.draw(frame, self)
        self._draw_escape_dust(frame)
        if self.anim and self.anim['kind'] == 'capture':
            self._draw_capture(frame)
        hide_hud = bool(self.battle.result and not self.anim) or bool(self.anim and self.anim.get('effect', {}).get('hide_ui'))
        for layer in (() if hide_hud else (self._hud_layer(True), self._hud_layer(False))):
            if layer:
                frame.alpha_composite(layer)
        draw = ImageDraw.Draw(frame, 'RGBA')
        if not hide_hud:
            self._draw_bars(draw)
            self._draw_status(frame, draw, self.presentation_unit(True), True)
            self._draw_status(frame, draw, self.presentation_unit(False), False)
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
        if self.info:
            layer, _, _ = self._crop_layout('SkillInfoNode', {'info_Text': self.info},
                                            offset=(W*.35, H*.35))
            if layer:
                frame.alpha_composite(layer, ((W-layer.width)//2, (H-layer.height)//2))
        self.frame = frame
        return frame

    def _draw_pet(self, frame, unit, center, height, enemy=False, flash=0.0):
        fleeing = bool(unit and self.anim and self.anim.get('kind') == 'escape'
                       and self.anim.get('source_uid') == unit.pet.uid)
        pending_flee = bool(unit and any(action.get('kind') == 'escape'
                                        and action.get('source_uid') == unit.pet.uid
                                        for action in self.anim_queue))
        if not unit or (getattr(unit, 'fled', False) and not fleeing and not pending_flee):
            return
        # Pet.scale is applied to both the setup pose and every spine frame in
        # OriginalData; the battle target height must carry it as well or the
        # two scalings cancel and every pet draws at the same size.
        pet_scale = float(self.app.data.tables['Pet'][unit.pet.species].get('scale', 1) or 1)
        height = max(1, round(height*pet_scale))
        appearance_alpha = 1.0
        if self.opening_frame is not None and ('enemy' if enemy else 'player') in self._entry_ball_sides():
            age = self.opening_frame-self.opening_transition
            scale, dy, appearance_alpha = self._appearance_pose(age-self._entry_plan('enemy' if enemy else 'player')['reveal'])
            if scale <= 0:
                return
            height = max(1, round(height*scale))
            center = (center[0], center[1]-round(dy*W/800))
        if self.battle.result and not self.anim and not unit.alive:
            return
        if enemy and self.anim and self.anim['kind'] == 'capture':
            fi = self.anim['age']*60/25
            scale, center, appearance_alpha = self._capture_pose(fi, center)
            if scale <= 0:
                return
            height = max(1, round(height*scale))
        setup = self.app.data.pet_image(unit.pet.species)
        if setup is None:
            return
        clip, age, loop = 'stand', self.anim_idle, True
        side = 'enemy' if enemy else 'player'
        faint_t = None
        if self.anim and self.anim['kind'] == 'faint' and self.anim['side'] == side:
            faint_t = min(1.0, self.anim['age']/max(1.0, self.anim['duration']))
            if faint_t >= 1:
                return
            center = (center[0], center[1]+round(28*faint_t))
            if self.app.data.pet_clip_duration(unit.pet.species, 'dead') > 0:
                clip, age, loop = 'dead', self.anim['age'], False
        elif self.anim and self.anim['kind'] == 'switch' and self.anim['side'] == side:
            scale, dy, appearance_alpha = self._appearance_pose(self.anim['age']*60/25-self._entry_plan(side)['reveal'])
            if scale <= 0:
                return
            height = max(1, round(height*scale))
            center = (center[0], center[1]-round(dy*W/800))
        elif fleeing:
            height = max(1, round(height*(1-.6*min(1, self.anim['age']/10))))
        if self.anim and self.anim['kind'] in ('attack', 'skill') and self.anim['side'] == side and not self.anim.get('idle'):
            clip, age, loop = 'attack', self.anim['age'], False
        elif self.anim and self.anim.get('impact', {}).get('side') == side and self.anim['impact']['type'] == 'damage':
            clip, age, loop = 'underattack', self.anim['age']-self.anim['impact']['when'], False
        fps = 30
        pose_frame = int(age*fps/25)
        duration = self.app.data.pet_clip_duration(unit.pet.species, clip)
        if duration > 0:
            pose_frame = pose_frame % max(1, math.ceil(duration*fps)) if loop else min(pose_frame, math.ceil(duration*fps))
        pose_key = (unit.pet.species, clip, pose_frame, loop, height, enemy)
        cached = self._pose_cache.get(pose_key) if not flash else None
        if cached is not None:
            image, origin, points = cached
            if faint_t is not None:
                image = self._faint_image(image, faint_t)
            image = self._opacity(image, appearance_alpha)
            image = pet_flash(self.app.data, unit.pet.species, image,
                              self.anim_idle/25, getattr(unit.pet, 'shiny', False))
            self.pet_bones[side] = {key: (center[0]+p[0], center[1]+p[1]) for key, p in points.items()}
            frame.alpha_composite(image, (round(center[0]-origin[0]), round(center[1]-origin[1])))
            self._pose_cache.move_to_end(pose_key)
            return
        limit = max(300, min(550, round(550*height/setup.height)))
        image = self.app.data.pet_frame(unit.pet.species, clip, pose_frame, loop, fps=fps, limit=limit)
        if image is None:
            image = setup
        ratio = height/max(1, setup.height)*setup.info.get('pixels_per_unit', 1)/image.info.get('pixels_per_unit', 1)
        self.pet_bones[side] = {key: (center[0]+point[0]*ratio*(-1 if not enemy else 1),
                                      center[1]+point[1]*ratio)
                                for key, point in image.info.get('bone_points', {}).items()}
        origin = image.info.get('origin', (image.width/2, image.height))
        origin = (origin[0]*ratio, origin[1]*ratio)
        image = image.resize((max(1, round(image.width*ratio)), max(1, round(image.height*ratio))), Image.Resampling.LANCZOS)
        if not enemy:
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            origin = (image.width-origin[0], origin[1])
        points = {key: (p[0]-center[0], p[1]-center[1]) for key, p in self.pet_bones[side].items()}
        self._pose_cache[pose_key] = (image, origin, points)
        if len(self._pose_cache) > 128:
            self._pose_cache.popitem(last=False)
        if faint_t is not None:
            image = self._faint_image(image, faint_t)
        image = self._opacity(image, appearance_alpha)
        image = pet_flash(self.app.data, unit.pet.species, image,
                          self.anim_idle/25, getattr(unit.pet, 'shiny', False))
        if flash:
            overlay = Image.new('RGBA', image.size, (255, 48, 32, 255))
            image = Image.blend(image, overlay, min(.55, .55*flash))
        frame.alpha_composite(image, (round(center[0]-origin[0]), round(center[1]-origin[1])))

    @staticmethod
    def _opacity(image, alpha):
        if alpha >= .999:
            return image
        image = image.copy()
        image.putalpha(image.getchannel('A').point(lambda v: round(v*alpha)))
        return image

    @staticmethod
    def _faint_image(image, progress):
        opacity = max(0.0, 1.0-max(0.0, progress-.5)/.5)
        if opacity >= .999:
            return image
        faded = image.copy()
        faded.putalpha(faded.getchannel('A').point(
            lambda value: round(value*opacity)))
        return faded

    def _draw_escape_dust(self, frame):
        """Original particle/escape.plist dust behind a fleeing pet."""
        if not self.anim or self.anim.get('kind') != 'escape':
            return
        from particles import draw_emitter
        path = self.app.data.assets/'particle/escape.plist'
        if not path.is_file():
            return
        elapsed = max(0.0, self.anim['age']/25)
        side = self.anim.get('side', 'player')
        x, y = self.pet_positions[side]
        source, target, _ = self._animation_offsets()
        enemy_offset = source if self.anim['side'] == 'enemy' else target
        player_offset = source if self.anim['side'] == 'player' else target
        dx, dy = enemy_offset if side == 'enemy' else player_offset
        # The native emitter is attached to the fleeing pet, not its old
        # anchor, so the dust has to travel with the spline.
        draw_emitter(frame, path, (x+dx, y+dy-12), (1.0, 1.0), elapsed)

    def _entry_ball_sides(self):
        """Wild pets are already present in X; trainers send out both pets."""
        return ('player',) if self.battle.kind == 'wild' else ('player', 'enemy')

    @lru_cache(maxsize=2)
    def _entry_plan(self, side):
        # Native executeAction + completion callback @ 2d2cf8 / 2d2980:
        # appearance arrays at 7cf078: [6,2,1,3,5], [8,2,1,3,5].
        _, source = self.app.data.armature_source('kaichong')
        moves = {m['name']: m for m in source['animation_data'][0]['mov_data']}
        suffix = '' if side == 'player' else '_0.8'
        segments, start, reveal = [], 0, None
        for index in ((6, 2, 1, 3, 5) if side == 'player' else (8, 2, 1, 3, 5)):
            name = f'Animation{index}{suffix}'
            move = moves[name]
            segments.append((name, start, int(move['dr'])))
            for bone in move.get('mov_bone_data', []):
                for event in bone.get('frame_data', []):
                    if event.get('evt') == 'out':
                        reveal = start+int(event['fi'])
            start += int(move['dr'])
        return {'segments': tuple(segments), 'reveal': reveal, 'duration': start}

    @staticmethod
    def _appearance_pose(age):
        # Native out callback @ 2d1738: .6s rise/shrink/fade, then .7s
        # EaseBackInOut scale to 1 and fade to 255; tension=1 spline.
        if age < 0:
            return 0, 0, 0
        if age < 36:
            t = age/36
            phase = min(3.999999, t*4)
            i, f = int(phase), phase-int(phase)
            heights = (0, 125, 160, 125, 0)
            dy = heights[i]+(heights[i+1]-heights[i])*(3*f*f-2*f*f*f)
            return .1+.3*t, dy, 1-(155/255)*t
        t = min(1, (age-36)/42)
        s = 1.70158*1.525
        q = t*2
        back = q*q*((s+1)*q-s)/2 if q < 1 else ((q-2)**2*((s+1)*(q-2)+s)+2)/2
        return .4+.6*back, 0, (100+155*t)/255

    @lru_cache(maxsize=128)
    def _entry_art(self, name, age, side):
        from armature_composite import transform_art
        art = self.app.data.armature('kaichong', name, age, layered=True)
        return transform_art(art, W/800, mirror=side == 'player') if art is not None else None

    def _draw_entry_ball(self, frame, age, sides=None):
        for side in sides or self._entry_ball_sides():
            segment = next(((name, start) for name, start, duration in self._entry_plan(side)['segments']
                            if start <= age < start+duration), None)
            if segment is None:
                continue
            name, start = segment
            art = self._entry_art(name, int(age-start), side)
            if art is None:
                continue
            origin = art.info.get('origin', (art.width/2, art.height/2))
            x, y = self.pet_positions[side]
            composite(frame, art, (round(x-origin[0]), round(y+75*W/800-origin[1])))

    def _draw_appearance_flash(self, frame, side, age):
        elapsed = age-self._entry_plan(side)['reveal']
        if elapsed < 0:
            return
        art = self.effects._scaled_art('chuchongguang', int(elapsed), W/800)
        if art is not None:
            origin = art.info['origin']
            x, y = self.pet_positions[side]
            composite(frame, art, (round(x-origin[0]), round(y-origin[1])))

    @lru_cache(maxsize=2)
    def _capture_plan(self, success):
        # X ELF catch_success_seq / catch_failed_seq, PetController's
        # completion callback 2d2b2a and executeAction 2d2de6: both start at 7.
        _, source = self.app.data.armature_source('kaichong')
        moves = {m['name']: m for m in source['animation_data'][0]['mov_data']}
        sequence = (7,13,4,11,9) if success else (7,13,4,12,3,14)
        segments, events, start = [], [], 0
        for number in sequence:
            name = f'Animation{number}'
            move = moves[name]
            segments.append((name,start,int(move['dr'])))
            events.extend((start+int(f['fi']),f['evt'])
                          for bone in move.get('mov_bone_data', [])
                          for f in bone.get('frame_data', []) if f.get('evt'))
            start += int(move['dr'])
        closing = next(t for t,name in events if name == 'close')
        # close responds immediately on success (2d2112), after a 1.5s
        # delay on failure (2d2132), rather than at the end of the last clip.
        return {'segments':tuple(segments), 'events':tuple(events),
                'in':next(t for t,name in events if name == 'in'),
                'out':next((t for t,name in events if name == 'out'),None),
                'response':closing+(0 if success else 90)}

    @staticmethod
    def _capture_segment(plan, frame):
        for name,start,duration in plan['segments']:
            if frame < start+duration:
                return name,max(0,int(frame-start))
        name,start,duration = plan['segments'][-1]
        return name,duration-1

    def _capture_pose(self, frame, anchor):
        plan = self.anim['capture_plan']
        # Original in callback (2d1b58): 1.5s Shake, then .6s tension-1
        # spline to scene centre, ScaleTo(.1), FadeTo(20), then hide.
        incoming = frame-plan['in']-90
        outgoing = frame-plan['out'] if plan['out'] is not None else -1
        if incoming < 0:
            shake = frame-plan['in']
            if shake >= 0:
                # Shake::update (2bb7fe): horizontal uniform noise times t,
                # amplitude 20; stop restores the original position. Visual
                # sampling has its own seed and never consumes battle RNG.
                import random
                dx = random.Random(int(frame)).uniform(-20,20)*(shake/90)*W/800
                return 1,(anchor[0]+dx,anchor[1]),1
            return 1,anchor,1
        if outgoing < 0 and incoming >= 36:
            return 0,anchor,0
        centre = (W/2,H/2)
        if outgoing >= 0:
            if outgoing >= 36:
                return 1,anchor,1
            start,end,t = centre,anchor,outgoing/36
            scale,alpha = .1+.9*t,(20+235*t)/255
        else:
            start,end,t = anchor,centre,incoming/36
            scale,alpha = 1-.9*t,(255-235*t)/255
        # CardinalSplineBy tension=1 reduces to smoothstep per segment.
        dx,dy = end[0]-start[0],end[1]-start[1]
        points = ((0,0),(.25*dx,.25*dy-75*W/800),
                  (.5*dx,.5*dy-125*W/800),(.75*dx,.75*dy-75*W/800),(dx,dy))
        phase = min(3.999999,max(0,t)*4)
        index = int(phase)
        local = phase-index
        eased = local*local*(3-2*local)
        offset = tuple(points[index][i]+(points[index+1][i]-points[index][i])*eased for i in (0,1))
        return scale,(start[0]+offset[0],start[1]+offset[1]),alpha

    def _draw_capture(self, frame):
        name,local = self._capture_segment(self.anim['capture_plan'],self.anim['age']*60/25)
        art = self._entry_art(name,local,'player')
        if art is None:
            return
        origin = art.info['origin']
        scale = W/800
        # Controller 1 mirrors the armature at the enemy shadow minus 240.
        # Animation7 already contains the throw; don't move it a second time.
        point = self.pet_positions['enemy']
        point = (point[0]-240*scale,point[1])
        composite(frame,art,(round(point[0]-origin[0]),round(point[1]-origin[1])))

    def _draw_damage(self, draw):
        impact = self.anim.get('impact') if self.anim else None
        if not impact or int(impact.get('amount', 0)) <= 0:
            return
        half = impact['when']
        if self.anim['age'] < half:
            return
        phase = min(1.0, (self.anim['age']-half)/max(1, half))
        side = impact['side']
        x = round(self.pet_positions[side][0])
        y = round(self.pet_positions[side][1])-260
        y -= round(34*phase)
        healing = impact['type'] == 'heal'
        text = ('+' if healing else '-')+str(impact['amount'])
        if impact.get('crit'):
            text += ' 暴击!'
        self._label(draw, (x, y), text, 28 if impact.get('crit') else 24,
                    (112, 245, 138, 255) if healing else
                    (255, 236, 120, 255) if impact.get('crit') else (255, 92, 72, 255), 'mm')

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

    def _buff_icon(self, key):
        """SkillState.stateId selects the authored res/UI/buff_<id>.png."""
        key = str(key)
        if key not in self._buff_icons:
            row = self.app.data.tables.get('SkillState', {}).get(key, {})
            state_id = str(row.get('stateId', ''))
            icon = None
            if state_id:
                try:
                    icon = self.app.data.image(f'res/UI/buff_{state_id}.png')
                except (OSError, KeyError):
                    icon = None
            if icon is not None:
                icon = icon.resize((32, 28), Image.Resampling.LANCZOS)
            self._buff_icons[key] = icon
        return self._buff_icons[key]

    def _draw_status(self, frame, draw, unit, enemy):
        if not unit:
            return
        x = W*.52 if enemy else W*.04
        y = H*.09 if enemy else H*.70
        for index, buff in enumerate(unit.buffs[:6]):
            icon = self._buff_icon(buff.key)
            if icon is not None:
                top = y+index*30
                frame.alpha_composite(icon, (round(x), round(top)))
                self._label(draw, (x+31, top+27), str(buff.rounds), 12, anchor='rs')
                continue
            # Seven authored states have no buff_<stateId>.png; keep a readable
            # text badge for those instead of dropping the state entirely.
            name = buff.name or buff.kind
            bad = buff.kind in ('poison', 'drain', 'leech', 'nightmare', 'doom',
                                'sleep', 'petrify', 'freeze', 'fear')
            color = (170, 45, 45, 230) if bad else (50, 130, 70, 230)
            draw.rounded_rectangle((x, y+index*30, x+94, y+index*30+24), 4, fill=color)
            self._label(draw, (x+47, y+index*30+12), f'{name}{buff.rounds}', 13, anchor='mm')

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
        text, visible, resources = {}, {}, {}
        for index in range(1, 5):
            key = f'itemMenu_{index}_Button'
            if index <= len(rows):
                item_id, row, count = rows[index-1]
                visible[key] = True
                resources[f'Node/battleItemMenu_Panel/item_Panel/{key}/icon_Image'] = 'ItemIcon/'+row['texture']
                text[f'Node/battleItemMenu_Panel/item_Panel/{key}/nameBg_Image/name_Text'] = str(row.get('name', item_id))
                text[f'Node/battleItemMenu_Panel/item_Panel/{key}/have_BitmapFontLabel'] = str(count)
            else:
                visible[key] = False
        layer, origin, hits = self._crop_layout('BattleItemMenuNode', text, visible, resources,
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
                {'kind_Image': 'UI/'+kind}, colors={'name_Text': quality_color(unit.pet)})
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

    def _levelup_data(self):
        if self.levelup_entries is None:
            self.levelup_entries = []
            for name, gained, levels in self.battle.exp_gained:
                if levels:
                    self.levelup_entries.append({
                        'name': name,
                        'gained': gained,
                        'from_level': levels[0]-1,
                        'to_level': levels[-1],
                    })
        return self.levelup_entries

    def _levelup_active(self):
        return self.levelup_index < len(self._levelup_data())

    def _levelup_stats(self, entry, unit):
        """Return the five original attribute rows shown by PetLevelUpUI."""
        from copy import deepcopy
        before_pet = deepcopy(unit.pet)
        before_pet.level = max(1, int(entry['from_level']))
        before = before_pet.stats(self.app.data.tables)
        after = unit.pet.stats(self.app.data.tables)
        icons = ('life', 'energy', 'strength', 'defense', 'speed')
        return [(icon, current, current-before[index])
                for index, (icon, current) in enumerate(zip(icons, after))]

    def _draw_levelup(self, frame):
        entry = self._levelup_data()[self.levelup_index]
        name = entry['name']
        # The five trainAdd project nodes are prefab placeholders when a pet
        # has no training gain; without hiding them the original prefab text
        # ("生命训练值+99") is shown for every pet.
        hidden = {f'trainAdd_{index}_ProjectNode': False for index in range(1, 6)}
        # The exp bar is animated by PetLevelUpUILayer itself; a static
        # LoadingBar leaves only its clipped "0" visible behind the pet.
        hidden.update({'exp_Sprite': False, 'expBg_Sprite': False,
                       'exp_LoadingBar': False})
        unit = next((u for u in self.battle.player if u.name == name), None)
        layer = self.app.cocos_ui.render('PetLevelUpUI', (W, H),
            text={'name_Text': name, 'petName_Text': name,
                  'info_Text': '获得经验', 'exp_BitmapFontLabel': str(entry['gained']),
                  'levelFrom_BitmapFontLabel': str(entry['from_level']),
                  'levelTo_BitmapFontLabel': str(entry['to_level'])},
            visible=hidden, colors={'name_Text': quality_color(unit.pet), 'petName_Text': quality_color(unit.pet)} if unit else {},
            timeline_frame=int(min(489, self.levelup_age)))
        # The stat rows below are separate CocosUI renders and reset the shared
        # controls map, so capture the level-up panel's confirm button first.
        controls = dict(self.app.cocos_ui.buttons)
        frame.alpha_composite(layer)
        unit = next((u for u in self.battle.player if u.name == name), None)
        if unit is not None:
            art = self.app.data.pet_image(unit.pet.species)
            if art is not None:
                art = art.copy()
                art.thumbnail((210, 210), Image.Resampling.LANCZOS)
                art = pet_flash(self.app.data, unit.pet.species, art,
                                self.levelup_age/60, getattr(unit.pet, 'shiny', False))
                frame.alpha_composite(art, (round(W*.25-art.width/2),
                                            round(H*.52-art.height)))
            list_rect = self.app.cocos_ui.rects.get(
                'Layer/root_Panel/levelUp_Panel/listviewBg_Image/arrt_ListView')
            if list_rect:
                for index, (icon, current, gain) in enumerate(
                        self._levelup_stats(entry, unit)):
                    item = self.app.cocos_ui.render(
                        'PetLevelUpItemUI', (252, 34),
                        text={'current_BitmapFontLabel': str(current),
                              'add_BitmapFontLabel': f'+{gain}'},
                        resources={'name_Image':
                                   f'UI/text_attribute_{icon}.png'})
                    frame.alpha_composite(
                        item, (round(list_rect[0]),
                               round(list_rect[1]+index*34)))
        self.hits['result_continue'] = tuple(
            controls.get('confirm_Button', (W-170, H-80, W, H)))

    def _result_lines(self):
        lines = []
        for name, gained, levels in self.battle.exp_gained:
            lines.append(f'{name} 获得 {gained} 点经验。')
            if levels:
                lines.append(f'{name} 升到了 Lv.{levels[-1]}！')
        lines += [f'获得 {self._reward_name(item)} ×{amount}' for item, amount in self.battle.drops]
        outcome = {'win': 'battleWin', 'lose': 'battleLose'}.get(self.battle.result)
        if outcome:
            lines.insert(0, self.app.data.localized_text()[outcome])
        elif self.battle.result == 'enemy_escape':
            lines.insert(0, '野生宠物逃走了！')
        if self.battle.caught_pet:
            name = self.app.data.tables['Pet'][self.battle.caught_pet.species]['name']
            lines.insert(0, f'捕捉到了 {name}！')
        return lines

    def _draw_result(self, frame, draw):
        # WorldMonsterBattleResultUI is a world-boss ranking page, not the
        # normal battle settlement. Use the recovered outcome/calculation UI.
        result = self.battle.result
        if self.result_page == 'outcome' and self._levelup_active():
            self._draw_levelup(frame)
            return
        if result == 'enemy_escape':
            # The original wild-escape path has no success/fail panel; show the
            # authored calculation layer with the flee line instead of an
            # empty ChallengeResultUI.
            self.result_page = 'calculation'
            self.result_index = 0
            layer = self.app.cocos_ui.render('BattleCalculationUI', (W, H),
                text={'chat_Text': '野生宠物逃走了！'}, timeline_frame=60)
            frame.alpha_composite(layer)
        elif self.result_page == 'outcome':
            if result == 'caught' and self.battle.caught_pet:
                pet = self.battle.caught_pet
                stats = pet.stats(self.app.data.tables)
                text = {'name_Text': self.app.data.tables['Pet'][pet.species]['name'],
                        'lv_BitmapFontLabel': str(pet.level)}
                for name, value in zip(('Life', 'Energy', 'Strength', 'Defense', 'Speed'), stats):
                    text['arrt'+name+'_BitmapFontLabel'] = str(value)
                rarity = int(self.app.data.tables['Pet'][pet.species]['starLevel'])
                layer = self.app.cocos_ui.render('PetCatchedEffectUI', (W, H), text,
                    colors={'name_Text': quality_color(pet)},
                    visible={f'star_Sprite_{i}': i <= rarity for i in range(1, 6)},
                    timeline_frame=int(min(199, self.result_age)))
                art = self.app.data.pet_image(pet.species)
                if art is not None:
                    art = art.copy()
                    art.thumbnail((250, 250), Image.Resampling.LANCZOS)
                    art = pet_flash(self.app.data, pet.species, art,
                                    self.result_age/60, getattr(pet, 'shiny', False))
                    layer.alpha_composite(art, (round(W/2-art.width/2), round(H*.53-art.height)))
            else:
                layer = self.app.cocos_ui.render('ChallengeResultUI', (W, H),
                    visible={'success_Panel': result == 'win', 'fail_Panel': result == 'lose',
                             'rank_Panel': False, 'rankUp_Sprite': False, 'cool_Sprite': False},
                    resources={'success_Sprite': 'UI/RankChallenge/rankChallenge_shengli.png'}, native_resources=('success_Sprite',),
                    positions={'success_Sprite': (0, 0), 'fail_Sprite': (0, 0)},
                    timeline_frame=int(min(169, self.result_age)))
            frame.alpha_composite(layer)
        else:
            lines = self._result_lines()
            index = getattr(self, 'result_index', 0)
            text = lines[index] if index < len(lines) else '战斗结束。'
            layer = self.app.cocos_ui.render('BattleCalculationUI', (W, H),
                       text={'chat_Text': text}, timeline_frame=60)
            frame.alpha_composite(layer)
        # The original calculation layer advances on a screen tap.
        self.hits['result_continue'] = (0, 0, W, H)
        if result == 'caught':
            self.hits['result_continue'] = tuple(self.app.cocos_ui.buttons.get('confirm_Button', (W-150, H-85, W, H)))

    def _reward_name(self, item):
        row = (self.app.data.tables['Item'].get(str(item)) or
               self.app.data.tables['Money'].get(str(item)) or
               self.app.data.tables['Pet'].get(str(item)) or {})
        return row.get('name', str(item))

    def _draw_log(self, frame, draw):
        # Diagnostics live in the desktop status bar, not over the original HUD.
        return

    # -- input ---------------------------------------------------------------
    def click(self, x, y):
        if self.anim or self.opening_frame is not None:
            return None
        if self.info:
            self.info = ''
            return 'refresh'
        if self.battle.result:
            if self._levelup_active():
                if self._inside(self.hits.get('result_continue'), x, y):
                    self.levelup_index += 1
                    self.levelup_age = 0.0
                    self.frame = None
                    return 'refresh'
                return None
            if self._inside(self.hits.get('result_continue'), x, y):
                if self.battle.result == 'caught':
                    return 'finish'  # Native captured-pet confirmation closes this result.
                lines = self._result_lines()
                if self.result_page == 'outcome' and lines:
                    self.result_page, self.result_index = 'calculation', 0
                elif self.result_page == 'calculation' and getattr(self, 'result_index', 0)+1 < len(lines):
                    self.result_index += 1
                else:
                    return 'finish'
                self.frame = None
                return 'refresh'
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
                if str(item) in ('220004', '220005', '220006') and self.app.state.pet_free_slots() <= 0:
                    self.notice = '宠物携带栏和银行都已满，请先腾出位置。'
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
        """BattleShopUILayer: original cards and BuyConfirmUI inside the game."""
        if self.app.ui_open:
            return
        from event_runtime import Request
        self.app.battle_shop_view = None
        self.app.open_ui(Request('openui', 'battle-shop', 0,
                                {'parameters': {'uiid': 69}}))

    def _after_action(self):
        b = self.battle
        self._capture_events()
        if b.force_switch:
            self.screen = 'pets'
            self.notice = '请选择下一只宠物'
        elif b.result:
            self.screen = 'main'
            self.notice = ''
            if b.result in ('escape', 'enemy_escape') and not self.anim:
                unit = (b.player_active if b.result == 'escape'
                        else b.enemy_active)
                if unit is not None:
                    self.anim = {'side': 'player' if b.result == 'escape' else 'enemy',
                                 'target': 'player' if b.result == 'escape' else 'enemy',
                                 'kind': 'escape', 'source_uid': unit.pet.uid,
                                 'amount': 0, 'crit': False, 'age': 0,
                                 'duration': 10, 'damages': []}
                    self.frame = None
                    self._signature = None
            if b.result in ('win', 'caught'):
                b.apply_rewards(self.app.state)
        else:
            self.screen = 'main'
            self.notice = ''
        if hasattr(self.app, 'battle_action_complete'):
            self.app.battle_action_complete()
        return 'refresh'
