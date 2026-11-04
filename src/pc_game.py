"""Native host for the original-state runtime. Incomplete mechanics stop explicitly."""
from __future__ import annotations

import argparse
import json
import math
import re
import os
import time
import tkinter as tk
from game_overlay import GameOverlay, GameArtLabel
from functools import lru_cache
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk

from original_data import OriginalData
from pc_preview import Preview, data_root
from game_state import GameState, numbers
from event_runtime import EventRuntime, PendingMechanic, Request
from csb_render import CocosUI
from battle import make_npc_battle, make_wild_battle
from arena import ArenaProgress, make_arena_battle
from infinite_arena import InfiniteArenaProgress, make_infinite_arena_battle
from budokan import BudokanProgress, make_budokan_battle
from battle_ui import BattleUI
from activity_ui import ActivityUI
from original_pages import OriginalPages
from daily_tasks import DailyTasks
from achievements import Achievements
from task_progress import TaskProgress
from mounts import Mounts
from guide import Guide, GuideTarget
from story_motion import StoryMotion, FACES, destination
from scene_ui import SceneUI
from npc_motion import NpcMotion
from exit_markers import ExitMarkers
from mail_pages import MailPages
from skill_pages import SkillPages


class NativeGame(SkillPages, MailPages, OriginalPages, ActivityUI, ExitMarkers, Preview):
    TARGET_FPS = 60
    WIDTH, HEIGHT = 960, 576  # Uniform 1.2x of the original 800x480 design.
    DYNAMIC_SCENERY = True
    def __init__(self, root, data, *, show_opening=False):
        self.opening = None
        self.state = GameState(data.tables)
        self.cocos_ui = CocosUI(data)
        self.runtime = EventRuntime(data, self.state)
        self.runtime.on_finish = self.release_story_camera
        self.runtime.present_rewards = True
        self.booting = True
        self.runtime_error = ''
        self.display_request = None
        self.event_notice = ''
        self.wait_until = 0
        self.camera_focus = None
        self.camera_action = None
        self.player_visible = True
        self.player_sprite = self.state.sprite_id
        self.inside_areas = set()
        self.battle = None
        self.battle_ui = None
        self.battle_tips = []
        self.pending_wait = None
        self.ui_window = None
        self.ui_open = False
        self.task_page = None
        self.main_ui_visible = True
        self.teach_nodes = []
        self.encounter_distance = 0.0
        self.encounter_threshold = 0
        self._play_clock = time.monotonic()
        self.show_map_label = False
        self.data = data
        self.guide = Guide(self)
        self.ui_hits = {}
        self.ui_rects = {}
        self.ui_buttons = {}
        self.ui_button_text = {}
        self.ui_actions = {}
        self.ui_base_layer = None
        self.ui_hover = None
        self.ui_pressed = None
        self.ui_render_args = None
        self.ui_close_result = None
        self.ui_info = None
        self.ui_parameters = {}
        self.ui_tutorial_active = False
        self.ui_story_active = False
        self.accept_task_window = None
        self.accept_task_buttons = {}
        self.arena_summary = None
        self.chest_fx = None
        self.obstacle_fx = None
        self.running_session = None
        self.running_result = None
        self.running_race_token = None
        self.story_motion = StoryMotion(self)
        self.scene_ui = SceneUI(self)
        self.npc_motion = None
        self.scene_animation_time = 0.0
        self.player_walking = False
        super().__init__(root, data)
        self.booting = False
        self.npc_motion = NpcMotion(self)
        from game_viewport import GameViewport
        self.viewport = GameViewport(self)
        self.viewport.bind('<Button-1>', self.on_click)
        self.viewport.bind('<ButtonRelease-1>', lambda e: self.task_page_event('release', e))
        self.viewport.bind('<B1-Motion>', lambda e: self.task_page_event('motion', e))
        self.viewport.bind('<MouseWheel>', self.on_canvas_wheel)
        self.root.bind('<Destroy>', lambda e: self.audio.close() if e.widget is self.root else None, add='+')
        self.runtime.play_sound = self.audio.effect
        root.title('口袋妖怪 · 原生 PC 移植开发版 0.2.92（全系统还原进行中）')
        top = root.winfo_children()[0]
        top.destroy()
        for child in root.winfo_children():
            if isinstance(child, tk.Label):
                child.pack_forget()
        default_save = Path(os.environ.get('LOCALAPPDATA', str(Path.home())))/'PocketNativePC'
        self.save_path = Path(os.environ.get('POCKET_NATIVE_SAVE_DIR', str(default_save)))/'slot1.json'
        from game_diagnostics import install_callback_log
        install_callback_log(self)
        self.autosave_job = root.after(30000, self.autosave)
        root.protocol('WM_DELETE_WINDOW', self.close_game)
        if self.save_path.exists() and self.restore():
            return
        if show_opening:
            clips = self.cocos_ui.layout('OpeningUI')['action']['clips']
            self.opening = (tuple(clips[f'animation{i}'] for i in range(7)), 0, time.monotonic())
            return
        self.start_prologue()

    def start_prologue(self):
        self.opening = None
        self.load_map(7401, 17*64+32, (30-14)*64)
        self.reset_encounter()
        self.runtime.notify('tomap', map=7401)
        self.drive()

    def opening_input(self, *, skip=False):
        clips, index, started = self.opening
        now = time.monotonic()
        begin, end = clips[index]
        if skip or index >= len(clips)-2 and (now-started)*60 >= end-begin:
            self.start_prologue()
        elif (now-started)*60 >= end-begin:
            self.opening = (clips, index+1, now)

    def load_map(self, mid, x=None, y=None):
        super().load_map(mid, x, y)
        self.map_name_started = None
        self.story_face_icons = {}
        self.story_face_until = 0
        if hasattr(self, 'state'):
            self.apply_scenery_visibility()
        self.screen_black = False
        self.screen_fade_until = 0
        self.chest_fx = None
        self.obstacle_fx = None
        self.treasure_search_fx = None
        self._apply_removed_obstacles()
        if hasattr(self, 'state') and not self.booting:
            self.state.map_id, self.state.x, self.state.y = self.map_id, self.x, self.y
            if self.map_id not in self.state.visited_maps:
                self.state.visited_maps.append(self.map_id)
            self.camera_focus = None
            self.camera_action = None
            self.player_visible = True
            self.inside_areas = set()
            self._processed_area_tile = None
            if getattr(self, 'npc_motion', None):
                self.npc_motion.reset()
            self.encounter_distance, self.encounter_threshold = 0.0, 0
            self.reset_encounter()

    def reset_encounter(self):
        row = self.data.tables['VillageMap'].get(str(self.map_id), {})
        interval = [int(v) for v in str(row.get('enemyAppearInterval', '0')).split(',') if v]
        if str(row.get('enemyIds', '0')) == '0' or not interval:
            self.encounter_threshold = 0
            return
        low = interval[0]
        high = interval[-1] if len(interval) > 1 else interval[0]
        self.encounter_threshold = self.state.rng.randint(min(low, high), max(low, high))

    def use_perfume(self, kid):
        _, steps, seconds = numbers(self.data.tables['FunctionItem'][str(kid)]['parameters'])
        with self.state.transaction():
            self.state.consume([kid], [1])
            self.state.activities['perfume'] = {'item': str(kid), 'steps': steps, 'until': time.time()+seconds}

    def apply_scenery_visibility(self):
        prefix = f'{self.map_id}:5:'
        self.map.set_hidden_scenery({key[len(prefix):] for key, visible in self.state.visible.items()
                                     if key.startswith(prefix) and not visible})

    def _apply_removed_obstacles(self):
        entries = getattr(getattr(self, 'state', None), 'removed_obstacles', [])
        changed = False
        for entry in entries:
            try:
                map_id, tx, ty = int(entry[0]), int(entry[1]), int(entry[2])
            except (TypeError, ValueError, IndexError):
                continue
            if map_id != self.map_id:
                continue
            if self.map.remove_obstacle(tx, ty) is not None:
                changed = True
        if changed and not self.DYNAMIC_SCENERY:
            self.background = self.map.render(self.SCALE, include_objects=False)

    def break_obstacle(self, obs_type, tx, ty):
        """Break/cut an obsType sprite only when the current ride has the ability."""
        mounts = Mounts(self.state)
        if not mounts.obstacle_ability(obs_type):
            return False
        if self.map.remove_obstacle(tx, ty) is None:
            return False
        self.state.removed_obstacles.append([int(self.map_id), int(tx), int(ty), int(obs_type)])
        if not self.DYNAMIC_SCENERY:
            self.background = self.map.render(self.SCALE, include_objects=False)
        self.obstacle_fx = {'x': int(tx)*self.map.tw+self.map.tw/2,
                            'y': int(ty)*self.map.th+self.map.th/2,
                            'type': int(obs_type), 'age': 0}
        TaskProgress(self.state).update('obstacle', int(obs_type))
        return True

    def move_to(self, x, y):
        before = (self.x, self.y)
        mounts = Mounts(self.state)
        if self.noclip:
            return super().move_to(x, y)
        if self.map.blocked(x, y, mounts):
            tx, ty = int(x//self.map.tw), int(y//self.map.th)
            obs_type = self.map.obstacle_at(x, y)
            if obs_type and self.break_obstacle(obs_type, tx, ty):
                if self.map.blocked(x, y, mounts):
                    return
            else:
                return
        if not mounts.enter(self.map.terrain_at(x, y), int(self.map.info['mapType'])):
            return
        self.x, self.y = x, y
        dx, dy = x-before[0], y-before[1]
        if dx or dy:
            self.player_walking = True
            if dx:
                self.face = 'standleft' if dx < 0 else 'standright'
            elif not getattr(self, 'keys', set()) & {'left', 'right', 'a', 'd'}:
                self.face = 'standup' if dy < 0 else 'standdown'

    def movement_speed(self):
        row = Mounts(self.state).active()
        # VillagePlayerControler::setMoveSpeed @ 0x2e0b5c.
        return 320.0 * (int(row['speed'])/100 if row else 1)

    def mounts_ui(self):
        if self.battle or self.runtime.running or self.ui_open:
            return
        self.scene_ui.toggle('left')

    def check_encounter(self):
        if self.battle or self.runtime.running or self.ui_open or self.display_request or self.pending_wait:
            return False
        perfume = self.state.activities.get('perfume', {})
        steps = int(perfume.get('steps', 0)) if float(perfume.get('until', 0)) > time.time() else 0
        if self.encounter_threshold <= 0 or self.encounter_distance < max(1, self.encounter_threshold+steps)*64:
            return False
        row = self.data.tables['VillageMap'][str(self.map_id)]
        ids = [v for v in row['enemyIds'].split(',') if v and v != '0']
        weights = [max(1, int(v)) for v in row['enemyProbability'].split(',') if v]
        if not ids:
            return False
        if len(weights) < len(ids):
            weights += [1]*(len(ids)-len(weights))
        enemy_id = self.state.rng.choices(ids, weights=weights[:len(ids)], k=1)[0]
        self.encounter_distance = 0.0
        self.reset_encounter()
        try:
            started = self.start_battle(enemy_id, 'wild')
        except PendingMechanic as error:
            self.runtime_error = str(error)
            return False
        return bool(started)

    def play_event(self, filename):
        if self.booting:
            return
        if self.runtime.running:
            return
        self.event_notice = ''
        self.runtime.start(filename)
        self.drive()

    def actors(self):
        if not hasattr(self, 'state') or self.booting:
            return super().actors()
        result = []
        for obj in self.map.objects:
            if obj['group'] != 'spriteLayer' or not obj.get('gid'):
                continue
            oid = obj.get('name', '')
            sid = self.map.tile_properties(int(obj['gid'])).get('spriteId')
            if not sid:
                continue
            # TMX NPC and chest groups reuse numeric names (e.g. 10502).
            # They are separate native controller types, never the same actor.
            kind = 3 if str(sid) == '30001' else 2
            key = f'{self.map_id}:{kind}:{oid}'
            from npc_visibility import value as npc_visible
            visible = npc_visible(self.state,self.map_id,kind,oid,
                                  int(obj['props'].get('state','1')) != 0)
            if not visible:
                continue
            x, y = self.state.positions.get(key, (float(obj['x'])+32, float(obj['y'])))
            result.append((oid, sid, x, y))
        for key, row in self.state.temp_npcs.items():
            if row['map'] == self.map_id and row['visible']:
                result.append(('temp:'+key, str(row['spriteid']), row['x'], row['y']))
        from treasure import TreasureHunt
        chest_table = self.data.tables.get('TChest', {})
        for entry in TreasureHunt(self.state).visible_on(self.map_id):
            sprite = str(chest_table.get(str(entry.get('chest_id')), {}).get('spriteId', '30002'))
            result.append((f'treasure:{entry["pos_id"]}', sprite, entry['x'], entry['y']))
        if getattr(self, 'chest_fx', None):
            result.append(('fx:treasure', self.chest_fx['sprite'],
                           self.chest_fx['x'], self.chest_fx['y']))
        return result

    def actor_animation(self, oid, sid):
        if str(sid) == '30001' and hasattr(self, 'state'):
            return 'opened' if str(oid) in self.state.activities.get('village_chests', []) else 'closed'
        if str(oid).startswith('treasure:'):
            return 'closed'
        if str(oid) == 'fx:treasure':
            return 'opened'
        kind, identifier = (7, str(oid)[5:]) if str(oid).startswith('temp:') else (2, oid)
        if getattr(self, '_actor_lookup_map', None) is not self.map:
            self._actor_lookup_map = self.map
            self._actor_lookup = {}
            for obj in self.map.objects:
                if obj.get('group') == 'spriteLayer' and obj.get('gid'):
                    self._actor_lookup.setdefault(str(obj.get('name')), obj)
        obj = self._actor_lookup.get(str(oid), {})
        # Some original TMX actors explicitly contain face="". Treat that as
        # the same default as a missing field, rather than stopping Tk redraw.
        fallback = FACES.get(int(obj.get('props', {}).get('face') or 2), 'standdown')
        ambient = getattr(self, 'npc_motion', None)
        if ambient and any(str(a['id']) == str(identifier) for a in ambient.motion.actions):
            return ambient.motion.animation(kind, identifier, fallback)
        return self.story_motion.animation(kind, identifier, fallback)

    def scene_sprite(self, sid, animation):
        frame = int(getattr(self, 'scene_animation_time', 0)*60) if animation.startswith(('walk', 'stand')) else 0
        return self.data.village_sprite(sid, animation, frame)

    def render_actor_overlay(self, frame, oid, sid, sx, sy, sprite, anchor):
        if self.booting or self.runtime.running or not str(oid).isdigit() or not str(sid).isdigit() or not 20000 <= int(sid) < 30000:
            return
        from task_icons import TaskIcons
        resolver = getattr(self, 'task_icons', None)
        if resolver is None or resolver.state is not self.state:
            resolver = self.task_icons = TaskIcons(self.state)
        icon_id = resolver.for_npc(oid)
        if icon_id:
            path = f'TaskIcon/taskIcon{icon_id}.png'
        else:
            default_face = self._actor_lookup.get(str(oid), {}).get('props', {}).get('defaultFace')
            if not default_face or not 1 <= int(default_face) <= 18:
                return
            path = f'FaceIcon/face1_{default_face}.png'
        icon = self._world_icon(path, self.SCALE*.5)
        bob = resolver.bob(getattr(self, 'scene_animation_time', 0))*self.SCALE
        top = sy-anchor[1]*self.SCALE-icon.height+bob
        frame.alpha_composite(icon, (round(sx-icon.width/2), round(top)))

    @lru_cache(maxsize=64)
    def _world_icon(self, path, scale):
        icon = self.data.image(path)
        return icon.resize((max(1, round(icon.width*scale)), max(1, round(icon.height*scale))), Image.Resampling.LANCZOS)

    def render_world_overlay(self, frame, camx, camy):
        guide = getattr(self, 'guide', None)
        if not guide or not guide.active or not guide.waypoints or self.runtime.running or self.battle:
            return
        dot = self.data.image('Sprite/dianji_path.png')
        dot = dot.resize((max(1, round(dot.width*self.SCALE)), max(1, round(dot.height*self.SCALE))), Image.Resampling.LANCZOS)
        for x, y in guide.waypoints[:-1]:
            sx, sy = x*self.SCALE-camx, y*self.SCALE-camy
            if -20 <= sx <= self.WIDTH+20 and -20 <= sy <= self.HEIGHT+20:
                frame.alpha_composite(dot, (round(sx-dot.width/2), round(sy-dot.height/2)))
        x, y = guide.waypoints[-1]
        marker = self.data.armature('dianji', 'Animation1', int(getattr(self, 'scene_animation_time', 0)*60))
        if marker is not None:
            anchor = marker.info.get('origin', (marker.width/2, marker.height/2))
            marker = marker.resize((max(1, round(marker.width*self.SCALE)), max(1, round(marker.height*self.SCALE))), Image.Resampling.LANCZOS)
            frame.alpha_composite(marker, (round((x-anchor[0])*self.SCALE-camx), round((y-anchor[1])*self.SCALE-camy)))

    def player_image(self, face):
        animation = self.story_motion.animation(1, 0, face)
        if animation.startswith('stand') and getattr(self, 'player_walking', False):
            animation = animation.replace('stand', 'walk')
        ride = Mounts(self.state).active()
        if ride:
            mirror = animation.endswith('right')
            clip = animation.replace('right', 'left') if mirror else animation
            frame = int(getattr(self, 'scene_animation_time', 0)*60)
            image = self.data.armature(ride['filePath'], clip, frame)
            if image is not None:
                if mirror:
                    origin = image.info.get('origin', (image.width/2, image.height))
                    image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                    image.info['origin'] = (image.width-origin[0], origin[1])
                return image
        return self.scene_sprite(self.player_sprite, animation)

    def show_purchase_notice(self, name, count):
        # RewardTipsUiLayer uses TipsUiNode, DelayTime(.5), FadeOut(.5).
        self.purchase_notice = (f'获得道具：{name} ×{count}', time.monotonic())
        job = getattr(self, 'purchase_notice_job', None)
        if job:
            self.root.after_cancel(job)
        def refresh():
            self.purchase_notice_job = None
            if not self.ui_open or not getattr(self, 'purchase_notice', None):
                return
            self._paint_hover()
            if self.purchase_notice:
                self.purchase_notice_job = self.root.after(33, refresh)
        refresh()

    def paint_purchase_notice(self, frame):
        notice = getattr(self, 'purchase_notice', None)
        if not notice:
            return
        text, started = notice
        age = time.monotonic()-started
        if age >= 1:
            self.purchase_notice = None
            return
        width = min(760, max(100, self.cocos_ui.font('', 30).getlength(text)+34))
        art = self.cocos_ui.render('TipsUiNode', frame.size, canvas_size=(800, 480),
            text={'tip_Text': text}, auto_text=('tip_Text',),
            positions={'bg_Image': (400, 84), 'tip_Text': (width/2, 29.5)},
            sizes={'bg_Image': (width, 59)}, alphas={'Node': round(255*min(1, (1-age)*2))})
        frame.alpha_composite(art)

    def search_treasure(self):
        from treasure import TreasureHunt
        hunt = TreasureHunt(self.state)
        current = hunt.active()
        if not current:
            raise ValueError('当前没有藏宝图。')
        sprite = self.data.tables['TChest'][current['chest_id']]['spriteId']
        box = json.loads(self.data.sprite_tiles()[sprite]['box'])
        x, y = self.camera_origin()
        viewport = (x/self.SCALE, y/self.SCALE, (x+self.WIDTH)/self.SCALE, (y+self.HEIGHT)/self.SCALE)
        found = hunt.use_magnifier(map_id=self.map_id, viewport=viewport, box=box)
        texts = json.loads((self.data.assets/'Data/Text.json').read_text(encoding='utf-8'))
        key = 'treasureTips3' if found else 'treasureTips4'
        self.treasure_search_fx = {'age': 0.0, 'text': next(row['text'] for row in texts if row['name'] == key)}
        return found

    def _draw_treasure_search(self, frame):
        fx = getattr(self, 'treasure_search_fx', None)
        if not fx:
            return
        index = int(fx['age']*60)
        if index < 61:
            art = self.data.armature('leida', 'Animation1', index)
            if art is not None:
                scale = self.WIDTH/800
                ox, oy = art.info.get('origin', (art.width/2, art.height/2))
                art = art.resize((max(1, round(art.width*scale)), max(1, round(art.height*scale))), Image.Resampling.LANCZOS)
                frame.alpha_composite(art, (round(self.WIDTH/2-ox*scale), round(self.HEIGHT/2-oy*scale)))
        # Original TipsUiNode grows its scale9 background with the text.
        # The authored 180px sample label otherwise clips the final characters.
        width = math.ceil(self.cocos_ui.font('', 30).getlength(fx['text']))+2
        tip = self.cocos_ui.render('TipsUiNode', (self.WIDTH, self.HEIGHT),
                                   text={'tip_Text': fx['text']},
                                   sizes={'bg_Image': (width+72, 59), 'tip_Text': (width, 34)},
                                   positions={'Node': (400, 240), 'tip_Text': ((width+72)/2, 29.5)})
        frame.alpha_composite(tip)

    def _draw_chest_fx(self, frame):
        fx = getattr(self, 'chest_fx', None)
        if not fx:
            return frame
        camx, camy = self.camera_origin()
        cx = fx['x']*self.SCALE-camx
        cy = fx['y']*self.SCALE-camy
        age = fx.get('age', 0)
        fade = max(0.0, 1.0-age/26)
        draw = ImageDraw.Draw(frame, 'RGBA')
        # The original chest armature plays its opened clip; these short rays
        # and sparks make the successful find readable without inventing loot.
        glow = int(90*fade)
        for radius, alpha in ((58, glow//2), (40, glow)):
            draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius),
                         outline=(255, 224, 120, alpha), width=2)
        for index in range(12):
            angle = -math.pi/2 + index*math.pi/6
            length = 38+16*((index*7) % 5)
            x1 = cx+math.cos(angle)*20
            y1 = cy+math.sin(angle)*20
            x2 = cx+math.cos(angle)*length
            y2 = cy+math.sin(angle)*length
            draw.line((x1, y1, x2, y2), fill=(255, 246, 190, int(230*fade)), width=3)
        for index in range(10):
            angle = index*math.pi/5+age*.08
            radius = 30+12*((index*3+age) % 5)
            x2, y2 = cx+math.cos(angle)*radius, cy+math.sin(angle)*radius
            size = 2+index % 4
            draw.rectangle((x2-size, y2-size, x2+size, y2+size),
                           fill=(255, 250, 210, int(245*fade)))
        return frame

    def _draw_obstacle_fx(self, frame):
        fx = getattr(self, 'obstacle_fx', None)
        if not fx:
            return frame
        camx, camy = self.camera_origin()
        cx = fx['x']*self.SCALE-camx
        cy = fx['y']*self.SCALE-camy
        age = fx.get('age', 0)
        fade = max(0.0, 1.0-age/22)
        draw = ImageDraw.Draw(frame, 'RGBA')
        color = (139, 94, 47) if fx.get('type') == 1 else (155, 151, 137)
        # Short-lived chips and dust after the original obsType object is
        # removed.  This is presentation only; the collision/task mutation is
        # already committed before the effect starts.
        dust = 18+age*2
        draw.ellipse((cx-dust, cy-dust*.55, cx+dust, cy+dust*.55),
                     outline=(210, 190, 150, int(80*fade)), width=2)
        for index in range(14):
            angle = index*math.pi*2/14+age*.035
            distance = 7+age*2.8
            px = cx+math.cos(angle)*distance
            py = cy-6+math.sin(angle)*distance*.7-age*age*.16
            size = max(1, 4-age//7)
            draw.rectangle((px-size, py-size, px+size, py+size),
                           fill=color+(int(235*fade),))
        return frame

    UI_LAYOUTS = {
        1: ('ShopUI', '商店'), 2: ('EvolutionShopUI', '材料商店'), 3: ('SkillShopUI', '卷轴商店'),
        4: ('PetBankUI', '宠物银行'), 5: ('HatchRoomUI', '孵化屋'), 6: ('SkillLearnUI', '技能学习'),
        7: ('ChooseFirstPetUI', '初始宠物'), 8: ('IllustratedPetInfoUI', '宠物图鉴'),
        9: ('AreaMapUI', '地区地图'), 10: ('ArenaInfoUI', '竞技场'),
        11: ('CureConfirmUI', '宠物治疗'), 12: ('ContinuousLoginUI', '连续登录'),
        13: ('TrialPetUI', '宠物使者'), 14: ('SaveConfirmUI', '保存进度'),
        15: ('TrialTowerUI', '道馆试练'), 16: ('BuyPetUI', '坐骑商店'),
        17: ('BuyPetUI', '宠物商店'), 18: ('MergePetUI', '宠物融合'),
        19: ('InfiniteArenaUI', '无限竞技场'), 20: ('InfiniteArenaEnterConfirmUI', '无限竞技场入场'),
        21: ('InfiniteArenaQuitConfirmUI', '无限竞技场退出'), 22: ('InfiniteArenaShopUI', '竞技场商店'),
        23: ('PetTuPoUI', '宠物突破'), 24: ('TreasureCheckUI', '神秘宝藏'),
        25: ('RunningPetWelUI', '赛宠嘉年华'), 26: ('RankUI', '排行榜'),
        27: ('GiftBagSaleUI', '礼包'), 28: ('MedalShopUI', '奖牌兑换'),
        29: ('RouletteUI', '幸运轮盘'), 30: ('CardLegendUI', '卡牌传说'),
        34: ('PetHeTiUI', '宠物合体'), 36: ('GiftBagSaleUI', '商店礼包'),
        37: ('TreasureBuyConfirmUI', '购买藏宝图'), 38: ('TreasureGetTipUI', '宝藏线索'),
        39: ('RunningPetWelUI', '赛宠嘉年华'), 40: ('RunningPetReadyUI', '赛宠押注'),
        41: ('RunningPetMapUI', '赛宠比赛'), 42: ('RunningPetResultUI', '赛宠结算'),
        43: ('BuyConfirmUI', '购买赛跑奖牌'),
        44: ('TaskUI', '每日任务'),
        45: ('AchievementUI', '成就'),
        46: ('BagUI', '背包'),
        47: ('PetListUI', '宠物'),
        48: ('IllustratedUI', '图鉴'),
        49: ('GetItemUI', '获得物品'),
        50: ('SecondConfirmUI', '二次确认'),
        51: ('TipConfirmUI', '提示'),
        52: ('ShopGoodsUI', '商品详情'),
        53: ('BuyConfirmUI', '购买确认'),
        54: ('SkillReplaceUI', '技能替换'),
        55: ('OpenChestConfirmUI', '开启宝箱'),
        56: ('FreePetConfirmUI', '放生确认'),
        57: ('PetPropertyUI', '宠物属性'),
        58: ('LuckyDrawPetInfoUI', '抽宠结果'),
        59: ('GameAboutUI', '关于'),
        60: ('SkillLearnConfirmUI', '技能学习确认'),
        61: ('EvolutionConditionUI', '进化条件'),
        62: ('HatchCheckUI', '孵化检查'),
        63: ('ShopUI', '金币商店'),
        68: ('LuckyDrawUI', '抽宠'),
        69: ('BattleShopUI', '战斗商店'),
        64: ('PublicNoticeUI', '公告'),
        65: ('SystemUI', '系统设置'),
        66: ('BluetoothListUI', '蓝牙'),
        67: ('AsideUI', '侧边栏'),
    }

    def open_ui(self, request):
        self.ui_story_active = False
        self.area_map_focus = None
        self.purchase_notice = None
        notice_job = getattr(self, 'purchase_notice_job', None)
        if notice_job:
            self.root.after_cancel(notice_job)
            self.purchase_notice_job = None
        job = getattr(self, 'ui_effect_job', None)
        if job and self.ui_window and self.ui_window.winfo_exists():
            self.ui_window.after_cancel(job)
        self.ui_effect_job = None
        parameters = request.data.get('parameters', {})
        if int(parameters.get('uiid', 0) or 0) == 53:
            self.shop_underlay = self.ui_base_layer.copy() if self.ui_base_layer else None
        self.ui_parameters = parameters
        self.original_page = None
        self.page_wheel = None
        self.page_drag = None
        self.page_drag_start = None
        uiid = int(parameters.get('uiid', 0) or 0)
        if uiid == 44:
            from task_page import TaskPage
            if self.ui_window and self.ui_window.winfo_exists():
                self.ui_window.destroy()
            self.ui_window, self.ui_open = None, True
            self.ui_hits, self.ui_rects, self.ui_buttons, self.ui_button_text = {}, {}, {}, {}
            self.ui_base_layer, self.ui_render_args = None, None
            self.keys.clear()
            self.task_page = TaskPage(self, parameters.get('page', 'main'))
            self.ui_info = tk.StringVar(value=self.task_page.info())
            self.ui_actions = {'receive_Button': self.task_page.receive,
                'close_Button': lambda: self.close_ui('no')}
            for i, page in enumerate(('main', 'branch', 'daily'), 1):
                self.ui_actions[f'tag_{i}_Button'] = lambda p=page: self.task_page.select_page(p)
            return
        self.task_page = None
        self.keys.clear()
        layout, name = self.UI_LAYOUTS.get(uiid, ('MainUI', f'原版界面 {uiid}'))
        if self.ui_window and self.ui_window.winfo_exists():
            self.ui_window.destroy()
        win = GameOverlay(self)
        win.title(f'{name} · 原版 Cocos 界面')
        win.transient(self.root)
        win.resizable(False, False)
        win.protocol('WM_DELETE_WINDOW', self.close_ui)
        self.ui_window, self.ui_open = win, True
        self.ui_actions, self.ui_hover, self.ui_pressed = {}, None, None
        self.ui_close_result = None
        try:
            layer = self.cocos_ui.render(layout, (800, 480), {})
            self.ui_render_args = {'name': layout, 'size': (800, 480), 'text': {},
                                   'visible': {}, 'resources': {}}
            self.ui_base_layer = layer.copy()
            self.ui_hits = dict(self.cocos_ui.hits)
            self.ui_rects = dict(self.cocos_ui.rects)
            self.ui_buttons = dict(self.cocos_ui.buttons)
            self.ui_button_text = dict(self.cocos_ui.button_text)
            photo = ImageTk.PhotoImage(layer)
            label = GameArtLabel(win, image=photo, bg='#101418', borderwidth=0)
            label.image = photo
            label.pack()
            label.bind('<ButtonPress-1>', self.on_ui_press)
            label.bind('<ButtonRelease-1>', self.on_ui_release)
            label.bind('<Motion>', self.on_ui_motion)
            label.bind('<Leave>', self.on_ui_leave)
            self.ui_art_label = label
        except (FileNotFoundError, ValueError, KeyError) as error:
            self.ui_hits, self.ui_rects, self.ui_buttons, self.ui_button_text = {}, {}, {}, {}
            self.ui_base_layer = None
            tk.Label(win, text=f'原 UI 布局读取失败：{error}', fg='#ffb0a0',
                     bg='#202b30').pack(padx=20, pady=20)
        body = tk.Frame(win, bg='#202b30')
        self.ui_body = body
        body.pack(fill='both', expand=True, padx=12, pady=8)
        info = tk.StringVar()
        self.ui_info = info
        tk.Label(body, textvariable=info, bg='#202b30', fg='#f2e7cf',
                 font=('Microsoft YaHei UI', 10), justify='left',
                 wraplength=760).pack(anchor='w')
        if uiid == 12:
            self._login_body(body, info)
        elif uiid == 11:
            currency, cost = self.state.cure_cost()
            from original_pages import Page
            page = Page(self, 'CureConfirmUI', timeline_frame=60,
                        text={'tips2_Text': '永久免费治疗全部携带宠物', 'times_BitmapFontLabel': '',
                              'cost_BitmapFontLabel': f'x{cost}'},
                        visible={'costTip_Text': currency == '700001',
                                 'cost_BitmapFontLabel': currency == '700001',
                                 'tips2_Text': currency != '700001',
                                 'times_BitmapFontLabel': False})
            page.publish()
            info.set(f'治疗全部携带宠物：{cost} {self.data.tables["Money"][currency]["name"]}' if currency else '医疗卡治疗免费。')
            def cure():
                try:
                    self.heal_party()
                    if self.runtime.pending and self.runtime.pending.kind in ('openui', 'wait'):
                        self.close_ui('yes')  # Continue the nurse's original healed dialogue.
                    else:
                        self._page_tip('全部携带宠物的生命和能量已恢复。', lambda: self.close_ui('yes'))
                except ValueError as error:
                    self._page_tip(str(error), lambda: self.open_ui(request))
            self.ui_actions['confirm_Button'] = cure
            self.ui_actions['cancel_Button'] = lambda: self.close_ui('no')
            body.pack_forget()
        elif uiid == 14:
            info.set(f'保存当前进度到本机用户目录：\n{self.save_path}')
            def save_now():
                if self.save():
                    self.close_ui('yes')
                else:
                    info.set(self.event_issue or '保存失败。')
                    if self.ui_window and self.ui_window.winfo_exists():
                        self.ui_window.title(self.event_issue or '保存失败')
            self.ui_actions['confirm_Button'] = save_now
            self.ui_actions['cancel_Button'] = lambda: self.close_ui('no')
            # SaveConfirmUI is a self-contained 800x480 original page; do not
            # append a host Tk form below it.
            body.pack_forget()
        elif uiid == 63:
            self._gold_store_page(body, info)
        elif uiid == 68:
            self._lottery_page(body, info)
        elif uiid == 64 and parameters.get('mailbox'):
            self._mail_page(body,info)
        elif uiid == 64:
            info.set('原版公告页。单机版没有联网公告服务，'
                     '这里不伪造运营公告；关闭后可继续游戏。')
            self.ui_actions['confirm_Button'] = self.close_ui
            self.ui_actions['close_Button'] = self.close_ui
            body.pack_forget()
        elif uiid == 65:
            info.set('F11 / Alt+Enter 切换全屏，Esc 返回窗口；音乐和音效开关立即生效。')
            self.ui_actions['close_Button'] = self.close_ui
            self.ui_actions['about_Button'] = self.about
            def control_mode(mode):
                # SystemUI's original click/direct toggle changes the mobile
                # movement input.  PC keyboard movement is always available;
                # persist the choice so a reopened page reports the same mode.
                self.state.presentation['input_mode'] = mode
                self.state.presentation['input_mode_note'] = (
                    '点击移动' if mode == 'click' else '方向控制')
                info.set(f'操作方式：{self.state.presentation["input_mode_note"]}。'
                         '电脑版方向键/WASD 与鼠标点击移动均可使用。')
            self.ui_actions['control_click_Button'] = lambda: control_mode('click')
            self.ui_actions['control_direct_Button'] = lambda: control_mode('direct')
            def sound_setting(kind, enabled):
                self.audio.set_enabled(kind, enabled)
                self.state.presentation[kind+'_enabled'] = enabled
                visibility = {
                    'music_open_Button': self.audio.music_enabled,
                    'music_close_Button': not self.audio.music_enabled,
                    'effect_open_Button': self.audio.effects_enabled,
                    'effect_close_Button': not self.audio.effects_enabled, 'moreGame_Button': False}
                self.ui_render_args['visible'] = visibility
                self.ui_base_layer = self.cocos_ui.render('SystemUI', (800, 480), visible=visibility)
                self.ui_hits = dict(self.cocos_ui.hits)
                self.ui_buttons = dict(self.cocos_ui.buttons)
                self.ui_art_label.set_layer(self.ui_base_layer)
            for kind in ('music', 'effect'):
                self.ui_actions[kind+'_open_Button'] = lambda k=kind: sound_setting(k, False)
                self.ui_actions[kind+'_close_Button'] = lambda k=kind: sound_setting(k, True)
            sound_setting('music', self.state.presentation.get('music_enabled', True))
            sound_setting('effect', self.state.presentation.get('effect_enabled', True))
            body.pack_forget()
        elif uiid == 66:
            info.set('原版蓝牙页。Windows 单机版不使用蓝牙联机，'
                     '这里不伪造附近玩家列表。')
            self.ui_actions['close_Button'] = self.close_ui
            body.pack_forget()
        elif uiid == 67:
            info.set('原版侧边栏。这里没有可用的联网侧边功能，'
                     '关闭后可继续游戏。')
            self.ui_actions['close_Button'] = self.close_ui
            body.pack_forget()
        elif uiid == 4:
            self._bank_body(body, info)
        elif uiid == 7:
            self._starter_body(body, info)
        elif uiid == 6:
            self._skill_body(body, info)
        elif uiid == 5:
            self._hatch_body(body, info)
        elif uiid in (16, 17):
            self._pet_shop_body(body, info, parameters.get('par1') or 601)
        elif uiid in (1, 2, 3, 22, 28, 69):
            self._shop_body(body, info, uiid)
        elif uiid == 29:
            self._roulette_body(body, info)
        elif uiid == 30:
            self._cards_body(body, info)
        elif uiid == 8:
            self._illustrated_body(body, info)
        elif uiid == 9:
            self._area_map_body(body, info)
        elif uiid == 10:
            self._arena_body(body, info, parameters.get('par1'), int(parameters.get('par2', 1) or 1))
        elif uiid == 13:
            self._trial_body(body, info)
        elif uiid == 15:
            self._budokan_body(body, info, parameters.get('par1') or 1)
        elif uiid == 25:
            self._running_body(body, info)
        elif uiid == 39:
            self._running_body(body, info)
        elif uiid == 40:
            self._running_ready_body(body, info)
        elif uiid == 41:
            self._running_race_body(body, info)
        elif uiid == 42:
            self._running_result_body(body, info)
        elif uiid == 43:
            self._running_medal_body(body, info)
        elif uiid == 45:
            self._achievement_body(body, info)
        elif uiid == 46:
            self._bag_body(body, info)
        elif uiid == 47:
            self._pet_list_body(body, info)
        elif uiid == 48:
            self._illustrated_overview_body(body, info)
        elif uiid == 49:
            self._get_item_body(body, info)
        elif uiid == 50:
            self._second_confirm_body(body, info)
        elif uiid == 51:
            self._tip_body(body, info)
        elif uiid == 52:
            self._shop_goods_body(body, info)
        elif uiid == 53:
            self._goods_confirm_body(body, info)
        elif uiid == 54:
            self._skill_replace_body(body, info)
        elif uiid == 55:
            self._open_chest_body(body, info)
        elif uiid == 56:
            self._free_pet_body(body, info)
        elif uiid == 57:
            self._pet_property_body(body, info)
        elif uiid == 58:
            self._lucky_pet_body(body, info)
        elif uiid == 59:
            self._about_body(body, info)
        elif uiid == 60:
            self._skill_learn_confirm_body(body, info)
        elif uiid == 61:
            self._evolution_body(body, info)
        elif uiid == 62:
            self._hatch_check_body(body, info)
        elif uiid == 26:
            self._rank_body(body, info)
        elif uiid in (19, 20, 21):
            self._infinite_body(body, info, uiid, parameters.get('par1'))
        elif uiid == 18:
            self._merge_body(body, info)
        elif uiid == 23:
            self._breakthrough_body(body, info)
        elif uiid == 24:
            self._treasure_page(body, info, parameters.get('par1'))
        elif uiid == 37:
            self._treasure_buy_body(body, info, parameters.get('par1'))
        elif uiid == 38:
            self._treasure_tip_body(body, info)
        elif uiid in (27, 36):
            self._gold_store_page(body, info)
        elif uiid == 34:
            self._fuse_body(body, info)
        else:
            info.set(f'{name}的交互尚未实现，当前仅显示原版布局。')
        tk.Button(body, text='关闭', command=self.close_ui).pack(side='bottom', pady=6)

    def ui_hit_at(self, x, y):
        """Return the topmost original Cocos button under an image-space point."""
        candidates = []
        for source, is_button in ((self.ui_buttons, True), (self.ui_hits, False)):
            for name, rect in source.items():
                if not (rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]):
                    continue
                # Both qualified and short names are recorded; prefer the full path.
                if '/' not in name and any(key.endswith('/'+name) for key in source):
                    continue
                area = max(1, (rect[2]-rect[0])*(rect[3]-rect[1]))
                actionable = self.ui_action_for(name) is not None or name.rsplit('/', 1)[-1] in {
                    'close_Button', 'closeButton', 'cancel_Button', 'cancelButton', 'leave_Button'}
                candidates.append((0 if actionable else 1, 0 if is_button else 1, area, name))
        if not candidates:
            return None
        name = min(candidates)[3]
        return name, self.ui_button_text.get(name, '')

    def ui_action_for(self, name):
        base = name.rsplit('/', 1)[-1]
        return self.ui_actions.get(name) or self.ui_actions.get(base)

    def on_ui_click(self, event):
        if not self.ui_window or not self.ui_window.winfo_exists():
            return
        if (self.ui_story_active and self.display_request
                and self.display_request.kind in ('talk', 'aside', 'airtalk', 'tapscreen')):
            self.interact()
            self.paint_modal_story()
            return
        hit = self.ui_hit_at(event.x, event.y)
        if not hit:
            return
        name, label = hit
        base = name.rsplit('/', 1)[-1]
        callback = self.ui_action_for(name)
        tutorial = False
        if self.display_request and self.display_request.kind == 'button' and self.ui_open:
            target = self._ui_tutorial_target(self.display_request.data.get('nodekey', ''))
            rect = self.ui_hits.get(target) if target else None
            tutorial = bool(rect and rect[0] <= event.x <= rect[2]
                            and rect[1] <= event.y <= rect[3])
            if rect and not tutorial and self.display_request.event == 'pEvent5905001.json':
                return
        if callback:
            try:
                completed = callback()
            except (ValueError, KeyError, PendingMechanic) as error:
                if self.ui_info:
                    self.ui_info.set(str(error))
                if getattr(self, 'original_page', None) is not None:
                    self._page_tip(str(error), self.original_page.publish)
                return
            if tutorial and completed is not False:
                self.advance_button_tip()
            return
        if base in {'close_Button', 'closeButton', 'leave_Button', 'cancel_Button',
                    'cancelButton', 'giveUp_Button', 'takeBack_Button'}:
            self.close_ui()
            return
        if self.ui_info:
            shown = label or base
            self.ui_info.set(f'原版按钮「{shown}」尚未接入对应玩法。')

    def on_ui_press(self, event):
        self.page_drag_start = (event.x, event.y)
        self.page_drag_moved = False
        hit = self.ui_hit_at(event.x, event.y)
        self.ui_pressed = hit[0] if hit else None
        self._paint_hover()

    def on_ui_release(self, event):
        self.page_drag_start = None
        if getattr(self, 'page_drag_moved', False):
            self.ui_pressed = None
            self._paint_hover()
            return
        hit = self.ui_hit_at(event.x, event.y)
        pressed = self.ui_pressed
        self.ui_pressed = None
        self._paint_hover()
        if hit and pressed == hit[0]:
            self.on_ui_click(event)

    def _paint_hover(self):
        if self.ui_story_active:
            self.paint_modal_story()
            return
        if not self.ui_base_layer or not hasattr(self, 'ui_art_label'):
            return
        if not self.ui_art_label.winfo_exists():
            return
        layer = None
        active = self.ui_pressed or (self.ui_hover[0] if self.ui_hover else None)
        if getattr(self, "original_page", None) is not None:
            layer = self.original_page.feedback(active)
        if layer is None and active and self.ui_render_args:
            # Prefer the original pressed texture for the button being pressed.
            pressed = {active: True}
            try:
                args = self.ui_render_args
                art = self.cocos_ui.render(args['name'], args['size'], args.get('text'),
                                           args.get('visible'), args.get('resources'), pressed=pressed)
                # Legacy custom pages own their dynamic contents; a button's
                # hover must never repaint the entire unpopulated prefab.
                layer = self.ui_base_layer.copy()
                rect = self.ui_buttons.get(active)
                if rect:
                    x, y, right, bottom = map(round, rect)
                    layer.paste(art.crop((x, y, right, bottom)), (x, y))
            except (FileNotFoundError, ValueError, KeyError):
                layer = None
        if layer is None:
            layer = self.ui_base_layer.copy()
            name = self.ui_pressed or (self.ui_hover[0] if self.ui_hover else None)
            rect = (self.ui_buttons.get(name) or self.ui_hits.get(name)) if name else None
            if rect:
                ImageDraw.Draw(layer).rectangle(
                    (round(rect[0]), round(rect[1]), round(rect[2]-1), round(rect[3]-1)),
                    outline='#ffe36e', width=3)
        self.ui_art_label.set_layer(layer)

    def on_ui_motion(self, event):
        start = getattr(self, 'page_drag_start', None)
        drag = getattr(self, 'page_drag', None)
        if start and drag:
            dx, dy = event.x-start[0], event.y-start[1]
            if abs(dx)+abs(dy) > 6:
                self.page_drag_moved = True
                self.page_drag_start = (event.x, event.y)
                drag(dx, dy)
                return
        hit = self.ui_hit_at(event.x, event.y)
        if hit == self.ui_hover:
            return
        self.ui_hover = hit
        self._paint_hover()

    def on_ui_leave(self, event=None):
        if self.ui_hover is not None:
            self.ui_hover = None
            self._paint_hover()

    def choose_starter(self, key):
        if self.state.starter_id:
            raise ValueError('已经选择了初始宠物。')
        row = self.data.tables['InitPet'][str(key)]
        species = str(row['petId'])
        pet = self.state.add_preset(str(key))
        self.state.starter_id = int(key)
        self.advance_main_condition('choose_pet', key)
        self.event_issue = f'选择了 {self.data.tables["Pet"][species]["name"]}！'
        self.close_transient_ui()
        if self.runtime.pending and self.runtime.pending.kind == 'openui':
            self.runtime.resume()
        self.drive()


    def open_goods_detail(self, shop_uiid, table, key, row):
        self.open_ui(Request('openui', 'shop-goods', 1, {
            'parameters': {'uiid': 52, 'table': table, 'key': key,
                           'shop_uiid': shop_uiid}}))

    def _back_to_shop(self, shop_uiid):
        # Returning from BuyConfirmUI is not closing the NPC's openui step.
        self.open_ui(Request('openui', 'shop-return', 1, {
            'parameters': {'uiid': shop_uiid, 'shop_return': True}}))

    def render_component(self, name, size=(800, 480), text=None, resources=None,
                         positions=None, visible=None):
        """Render a prefab layout on a full canvas instead of its tiny node size."""
        layout = self.cocos_ui.layout(name)
        root = layout['tree']
        old = root.get('size')
        root['size'] = list(size)
        try:
            return self.cocos_ui.render(name, size, text or {},
                                        visible=visible or {},
                                        resources=resources or {},
                                        positions=positions or {})
        finally:
            if old is None:
                root.pop('size', None)
            else:
                root['size'] = old



    def heal_party(self):
        self.state.cure_party()

    def accept_task_ui(self, request):
        """The original accept card, rewards and choices in the game surface."""
        from original_pages import Page
        from pet_pages import text_box
        key = str(request.data.get('parameters', {}).get('btask', ''))
        row = self.data.tables['BranchTask'].get(key)
        if not row:
            self.runtime.resume(False)
            self.drive()
            return
        self.open_ui(Request('openui', 'accept-task-panel', request.step,
                            {'parameters': {'uiid': 50}}))
        self.display_request = request
        scroll, limit = [0, 0], [0, 0]
        areas = [None, None]
        rewards = [(kid, n) for kid, n in zip(numbers(row['rewardIds']), numbers(row['rewardCounts'])) if kid and n]
        def paint():
            page = Page(self, 'AcceptBTaskUI', text={'name_Text': row['name'], 'info_Text': ''}, timeline_frame=60)
            areas[0] = next(r for k, r in page.rects.items() if k.endswith('/info_Text'))
            limit[0] = text_box(page, areas[0], row['des'], self.cocos_ui.font('', 15), scroll[0])
            area = areas[1] = next(r for k, r in page.rects.items() if k.endswith('/reward_ListView'))
            limit[1] = max(0, ((len(rewards)+1)//2)*110-(area[3]-area[1]))
            for i, (kid, count) in enumerate(rewards):
                name, icon = self._item_data(str(kid))
                page.add('RewardItemUI', (round(area[0]+(i%2)*96), round(area[1]+(i//2)*110-scroll[1])),
                         size=(96, 104), canvas_size=(96, 104), prefix=f'accept_reward_{i}/', clip=area,
                         text={'count_BitmapFontLabel': str(count), 'name_Text': name},
                         resources={'icon_Image': icon},
                         positions={'iconBg_Image': (38, 66), 'count_BitmapFontLabel': (8, 14)})
            page.actions.update({'accept_Button': lambda: finish(True), 'close_Button': lambda: finish(False)})
            page.publish()
            self._page_wheel(wheel)
        def wheel(event):
            x, y = event.x, event.y
            for i, rect in enumerate(areas):
                if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                    scroll[i] = max(0, min(limit[i], scroll[i]+(-24 if event.delta > 0 else 24)))
                    paint()
                    break
        def finish(choice):
            if self.runtime.pending is not request:
                return
            self.display_request = None
            self.close_transient_ui()
            self.runtime.resume(choice)
            self.drive()
        self._accept_task_finish = finish
        paint()
        self.ui_window.protocol('WM_DELETE_WINDOW', lambda: finish(False))


    def close_ui(self, result=None):
        self.ui_story_active = False
        lottery = getattr(self, 'lottery_animation', None)
        if lottery is not None:
            lottery.close()
            self.lottery_animation = None
        self.ui_tutorial_active = False
        job = getattr(self, 'ui_effect_job', None)
        if job and self.ui_window and self.ui_window.winfo_exists():
            self.ui_window.after_cancel(job)
        self.ui_effect_job = None
        wait_job = getattr(self, 'ui_wait_job', None)
        if wait_job:
            try:
                self.root.after_cancel(wait_job)
            except tk.TclError:
                pass
        self.ui_wait_job = None
        self.task_page = None
        choice = result if result in ('yes', 'no') else (self.ui_close_result or 'no')
        if self.ui_window and self.ui_window.winfo_exists():
            self.ui_window.destroy()
        self.ui_window, self.ui_open = None, False
        self.ui_hits, self.ui_buttons, self.ui_button_text = {}, {}, {}
        self.ui_rects = {}
        self.ui_actions, self.ui_base_layer, self.ui_hover, self.ui_info = {}, None, None, None
        self.ui_pressed, self.ui_render_args = None, None
        if self.battle and (int(self.ui_parameters.get('uiid', 0)) == 69
                            or self.ui_parameters.get('table') == 'BattleShop'):
            # Shopping is outside the turn and must not resume a pending fight.
            return
        pending = self.runtime.pending
        if self.pending_wait:
            self.pending_wait = None
            self.runtime.resume()
        elif pending and pending.kind == 'openui':
            # The following closeui step decides the no/yes branch.  Keep the
            # player's choice until that step is reached.
            self.ui_close_result = choice
            self.runtime.resume()
        elif pending and pending.kind == 'closeui':
            self.ui_close_result = None
            self.runtime.resume(choice)
        elif pending and pending.kind == 'reward':
            self.runtime.resume()
        self.drive()

    def key_down(self, event):
        if getattr(self, 'opening', None):
            key = event.keysym.lower()
            if key in ('escape', 'return', 'space'):
                self.opening_input(skip=key == 'escape')
            return
        panels = getattr(self, '_game_overlays', [])
        if panels:
            if event.keysym.lower() == 'escape':
                panels[-1].escape()
            return
        if self.ui_open and self.ui_window and self.ui_window.winfo_exists():
            if event.keysym.lower() == 'escape':
                self.ui_window._close()
            return
        if getattr(self, 'task_page', None):
            if event.keysym.lower() == 'escape':
                self.close_ui('no')
            return
        if self.battle:
            return
        key = event.keysym.lower()
        if key in ['space', 'return', 'e']:
            self.interact()
        elif key == 'f5':
            self.save()
        elif key == 'f9':
            self.restore()
        elif key == 'g':
            self.guide_toggle()
        elif key == 'b':
            self.bag_ui()
        elif key not in ['m', 'f3', 'escape']:
            if key in {'up', 'down', 'left', 'right', 'w', 'a', 's', 'd'}:
                self.guide.stop('已停止自动指引。')
            self.keys.add(key)

    def advance_main_condition(self, kind, value):
        TaskProgress(self.state).update(kind, int(value))

    def guide_toggle(self):
        if (self.battle or self.runtime.running or self.ui_open or self.display_request
                or self.pending_wait):
            return
        if self.guide.active:
            self.guide.stop('已停止自动指引。')
        else:
            TaskProgress(self.state).update()
            target = self.guide.refresh()
            if target:
                self.keys.clear()
                self.guide.start(target)

    def guide_shop(self, index):
        kind = self.scene_ui.SHOP_TYPES[int(index)-1]
        obj = self.scene_ui.shop_exits().get(kind)
        if obj is None:
            raise ValueError('当前地图没有这个设施的出口。')
        self.keys.clear()
        self.guide.start_click(float(obj['x'])+float(obj.get('width', 64))/2,
                               float(obj['y'])+float(obj.get('height', 64))/2)

    def guide_ui(self):
        if self.battle:
            self.event_issue = '战斗中不能自动前往，请先结束战斗。'
            return
        win = GameOverlay(self)
        win.title('任务指引 · 原生 0.2.92')
        win.transient(self.root)
        targets = self.guide.resolver.targets()
        text = tk.StringVar()
        tk.Label(win, textvariable=text, justify='left', anchor='w', wraplength=620,
                 font=('Microsoft YaHei UI', 10)).pack(fill='x', padx=10, pady=8)
        box = tk.Listbox(win, width=82, height=min(8, max(3, len(targets))),
                         font=('Microsoft YaHei UI', 10))
        box.pack(fill='both', expand=True, padx=10)
        for target in targets:
            box.insert('end', f'[{target.task_kind}] {target.label}')
        detail = tk.Text(win, width=82, height=6, wrap='word', font=('Microsoft YaHei UI', 10))
        detail.pack(fill='x', padx=10, pady=6)
        selected = {'target': targets[0] if targets else None}
        def show(_=None):
            if not box.curselection() or not targets:
                return
            target = targets[box.curselection()[0]]
            selected['target'] = target
            route = self.guide.graph.route(self.map_id, target.map_id) if target.map_id else []
            detail.delete('1.0', 'end')
            detail.insert('1.0', f'{target.detail}\n任务：{target.task_name or target.task_id}\n'
                                 f'{target.description}\n'
                                 f'目标地图：{target.map_id or "无"}  路线：{" → ".join(map(str, route)) or "无需移动"}')
            text.set(f'当前地图：{self.map_id} {self.map.info["name"]}\n'
                     f'自动前往时会沿原版出口逐图行走；按 G 再次停止。')
        def start():
            target = selected['target']
            if target:
                self.keys.clear()
                self.guide.start(target)
                detail.delete('1.0', 'end')
                detail.insert('1.0', self.guide.message)
        box.bind('<<ListboxSelect>>', show)
        if targets:
            box.selection_set(0)
            show()
        else:
            text.set(f'当前地图：{self.map_id} {self.map.info["name"]}\n'
                     '当前主线/支线没有可解析的空间目标。请先推进任务或检查任务条件。')
            detail.insert('1.0', '指引只使用原版任务表、地图事件区域和 NPC 对象；找不到对象时不会编造坐标。')
        buttons = tk.Frame(win)
        buttons.pack(fill='x', padx=10, pady=(0, 10))
        tk.Button(buttons, text='自动前往', command=start).pack(side='left')
        tk.Button(buttons, text='停止', command=lambda: self.guide.stop('已停止自动指引。')).pack(side='left', padx=6)
        tk.Button(buttons, text='关闭', command=win.destroy).pack(side='right')

    def interact(self, npc_id=None, sprite_id=None):
        if self.booting:
            return
        if self.display_request and self.display_request.kind in ['talk', 'aside', 'airtalk', 'tapscreen']:
            request = self.display_request
            self.dialogue = None
            self.display_request = None
            if self.runtime.pending is request:
                self.runtime.resume()
                self.drive()
            return
        if self.pending_wait:
            request = self.pending_wait
            wait_type = int(request.data.get('parameters', {}).get('type', 0) or 0)
            if wait_type == 2 and not self.ui_open:
                self.pending_wait = None
                if self.runtime.pending is request:
                    self.runtime.resume()
                self.drive()
            return
        if self.runtime.running or self.runtime_error:
            return
        actors = sorted(self.actors(), key=lambda a: (a[2]-self.x)**2+(a[3]-self.y)**2)
        # Native areaProcess uses eventLayer.npcId across solid counters.
        counter_ids = {str(o['props']['npcId']) for o in self.map.objects
                       if o['group'] == 'eventLayer' and o.get('props', {}).get('npcId')
                       and float(o['x']) <= self.x < float(o['x'])+float(o.get('width', self.map.tw))
                       and float(o['y']) <= self.y < float(o['y'])+float(o.get('height', self.map.th))}
        if npc_id is None and counter_ids:
            actors = [a for a in actors if str(a[0]) in counter_ids]
        if npc_id is not None:
            actors = [actor for actor in actors if str(actor[0]) == str(npc_id)]
        if sprite_id is not None:
            actors = [actor for actor in actors if str(actor[1]) == str(sprite_id)]
        if not actors or (str(actors[0][0]) not in counter_ids and
                          (actors[0][2]-self.x)**2+(actors[0][3]-self.y)**2 > 150**2):
            return
        oid = actors[0][0]
        if oid.startswith('temp:'):
            return
        if oid.startswith('treasure:'):
            from treasure import TreasureHunt
            try:
                chests = TreasureHunt(self.state)
                pos_id = oid.split(':', 1)[1]
                entry = next((e for e in chests.entries()
                              if str(e.get('pos_id')) == pos_id), None)
                item_id, count = chests.open(pos_id)
                row = (self.data.tables['Item'].get(str(item_id))
                       or self.data.tables['Pet'].get(str(item_id))
                       or self.data.tables['Money'].get(str(item_id), {}))
                if entry:
                    self.chest_fx = {'x': entry['x'], 'y': entry['y'],
                                     'sprite': str(self.data.tables.get('TChest', {})
                                                   .get(str(entry.get('chest_id')), {})
                                                   .get('spriteId', '30002')),
                                     'age': 0}
                self.show_reward('宝藏获得', [(item_id, count)])
            except (ValueError, KeyError) as error:
                self.event_issue = str(error)
            return
        if str(actors[0][1]) == '30001':
            from activities import Activities
            try:
                rewards = Activities(self.state).open_village_chest(oid)
                self.show_reward('宝箱获得', rewards)
            except (ValueError, KeyError) as error:
                self.event_issue = str(error)
                self.scene_ui.show_tip(str(error))
            return
        self.advance_main_condition('talk', oid)
        self.state.activities['talk_total'] = int(self.state.activities.get('talk_total', 0))+1
        if self.runtime.notify('talk', npcid=int(oid)):
            self.drive()
        else:
            fallback = self.data.root/'events'/f'pEventTalk{oid}.json'
            if fallback.exists():
                self.play_event(fallback.name)

    def next_step(self):
        if self.booting:
            return super().next_step()
        self.interact()

    def request_map(self, exit_id):
        """Original exit ids encode <map id><spawn suffix>, e.g. 722801 -> map 7228."""
        target = str(exit_id)
        mid = None
        for length in (2, 1):
            candidate = target[:-length]
            if candidate in self.data.tables['VillageMap']:
                mid = candidate
                break
        if mid is None:
            raise PendingMechanic(f'原出口 {target} 没有可解析的目标地图')
        destination = self.data.load_map(mid)
        found = [o for o in destination.objects
                 if o.get('name') == target and o['group'] == 'spriteLayer' and not o.get('gid')]
        if not found:
            raise PendingMechanic(f'原出口 {target} 在目标地图 {mid} 没有落点对象')
        obj = found[0]
        x, y = self.exit_spawn(destination, obj)
        self.load_map(mid, x, y)
        # PlotEventManager checks the arrival against the pre-arrival task
        # state. Otherwise task 14 becomes ready before pEvent115001 can start.
        self.runtime.notify('tomap', map=int(mid))
        self.advance_main_condition('map', int(mid))
        self.inside_areas = set()

    def try_exit(self):
        if self.booting:
            return super().try_exit()
        if self.runtime.running or time.monotonic() < self.exit_time:
            return
        for obj in self.map.objects:
            if obj['group'] != 'spriteLayer' or 'toExit' not in obj['props']:
                continue
            x, y = float(obj.get('x', 0)), float(obj.get('y', 0))
            w, h = float(obj.get('width', 64)), float(obj.get('height', 64))
            if x <= self.x < x+w and y <= self.y < y+h:
                try:
                    if self.runtime.notify('toexit', exit=int(obj['name'])):
                        self.drive()
                    else:
                        self.request_map(obj['props']['toExit'])
                except (PendingMechanic, ValueError) as error:
                    self.runtime_error = str(error)
                return

    def apply_visual(self, request):
        kind, parameter = request.kind, request.data.get('parameters', {})
        rows = parameter if isinstance(parameter, list) else [parameter]
        if kind == 'toplace':
            self.story_motion.begin(rows)
        elif kind in ['face', 'toface']:
            for p in rows:
                actor = int(p.get('spritetype', 2)), int(p.get('spriteid', 0))
                face = int(p.get('face', 0))
                if kind == 'face' and 1 <= face <= 8:
                    if not hasattr(self, 'story_face_icons'):
                        self.story_face_icons = {}
                    started = time.monotonic()
                    self.story_face_icons[actor] = (face, started)
                    self.story_face_until = started+2
                else:
                    self.story_motion.set_face(*actor, face)
        elif kind == 'tempnpc':
            for p in rows:
                point = destination(p, (self.x, self.y), self.face, (self.map.tw, self.map.th)) if 'x' in p and 'y' in p else None
                previous = self.state.temp_npcs.get(str(p['npcid']))
                if point is None:
                    point = (previous['x'], previous['y']) if previous and previous['map'] == self.map_id else (self.map.tw/2, self.map.th/2)
                self.state.temp_npcs[str(p['npcid'])] = dict(p, map=self.map_id,
                    x=point[0], y=point[1])
        elif kind == 'spritevisible':
            for p in rows:
                if p.get('spritetype') == 1:
                    self.player_visible = bool(p['visible'])
                elif p.get('spritetype') == 7:
                    if str(p['spriteid']) in self.state.temp_npcs:
                        self.state.temp_npcs[str(p['spriteid'])]['visible'] = int(p['visible'])
                else:
                    from npc_visibility import set_value
                    set_value(self.state,self.map_id,p.get('spritetype',2),
                              p.get('spriteid',0),p['visible'])
                    if int(p.get('spritetype', 2)) == 5:
                        self.apply_scenery_visibility()
        elif kind == 'screenmove':
            self.begin_camera_move(parameter)
        elif kind == 'tomap':
            self.request_map(parameter['exit'])
        elif kind == 'areamapmove':
            self.state.world_focus = int(parameter['map'])
            if self.ui_story_active and self.area_map_focus:
                self.area_map_focus(self.state.world_focus)
        elif kind == 'trialride':
            self.state.trial_ride = int(parameter['rideid'])
        elif kind == 'save':
            self.save()
        elif kind in ['screen', 'screenclose', 'screenflash', 'mainuivisible', 'addteachnode', 'closeui']:
            if kind in ['screen', 'screenclose']:
                self.screen_black = kind == 'screenclose' or int(parameter.get('type', 0)) == 0
                # showScreenSwitch @ 0x39d4b4 runs a half-second fade,
                # then invokes the plot callback. screenclose is immediate.
                if kind == 'screen':
                    self.screen_fade_until = time.monotonic()+.5
            elif kind == 'screenflash':
                self.flash_until = time.monotonic()+.2
            elif kind == 'mainuivisible':
                self.main_ui_visible = bool(parameter.get('visible', 1))
            elif kind == 'addteachnode':
                self.teach_nodes = []
            elif kind == 'closeui':
                if getattr(self, 'story_window', None) and self.story_window.winfo_exists():
                    self.story_window.destroy()
        else:
            raise PendingMechanic(f'原画面指令 {kind} 未实现')

    def on_click(self, event):
        if getattr(self, 'opening', None):
            bounds = getattr(self, '_opening_skip', None)
            skip = bool(bounds and bounds[0] <= event.x < bounds[2] and bounds[1] <= event.y < bounds[3])
            self.opening_input(skip=skip)
            return
        if getattr(self, '_game_overlays', []):
            return
        if getattr(self, 'task_page', None):
            self.task_page_event('press', event)
            return
        if self.battle and self.battle_ui:
            action = self.battle_ui.click(event.x, event.y)
            if action == 'finish':
                self.finish_battle()
            return
        if self.display_request and self.display_request.kind == 'button':
            self.advance_button_tip()  # Compatibility with an already displayed old lesson.
            return
        if not self.runtime.running and not self.ui_open and self.main_ui_visible:
            if self.scene_ui.click(event.x, event.y):
                return
        if self.runtime.running or self.display_request or self.pending_wait:
            self.interact()
            return
        if self.ui_open or self.runtime_error:
            return
        self.click_walk(event.x, event.y)

    def _ui_tutorial_target(self, key):
        """Resolve the original tutorial node key against the open page.

        Page actions retain full node paths because prefab cards repeat. The
        event files address a stable leaf name (for example use_Button,
        chooseItem_230011 or petSelectItem_1), so prefer exact aliases and then
        a unique visible leaf match.
        """
        if not self.ui_open:
            return None
        # HatchRoomUI repeats a prefab; native story keys use one-based slots.
        match = re.fullmatch(r'(putIn|check|takeBack)_Button_(\d+)', key)
        if match:
            prefix = f'hatch_{int(match[2])-1}/'
            matches = [name for name in self.ui_hits if name.startswith(prefix)
                       and name.endswith('/'+match[1]+'_Button') and self.ui_action_for(name)]
            return matches[0] if len(matches) == 1 else None
        if key.startswith('hatchRoomChooseItem_'):
            key = 'chooseItem_'+key[len('hatchRoomChooseItem_'):]
        if (key == 'hatch_Button' and self.runtime.file == 'pEvent5905001.json'
                and getattr(self, 'original_page', None)
                and any(name == 'HatchCheckUI' for name, *_ in self.original_page.specs)):
            key = 'hatch_Button' if self._hatch_ready(self.hatch_selection) else 'moneyHatch_Button'
        if key in self.ui_actions and key in self.ui_hits:
            return key
        matches = [name for name in self.ui_hits
                   if name.rsplit('/', 1)[-1] == key and self.ui_action_for(name)]
        return matches[0] if len(matches) == 1 else None

    def _button_target(self, key):
        if not key:
            return None
        if self.main_ui_visible and key in self.scene_ui.hits:
            return key
        return self._ui_tutorial_target(key)

    def _schedule_ui_wait(self, request, delay=220):
        # wait type 2 is the original UI opening/settling wait.  It must not
        # wait for the page to close: pEvent101006 buys inside the still-open
        # shop, chooses inside the still-open bag, etc.
        self.ui_tutorial_active = True
        job = getattr(self, 'ui_wait_job', None)
        if job:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self.ui_wait_job = None

        def poll():
            if self.pending_wait is not request or self.runtime.pending is not request:
                return
            # type 2 is a fixed UI/menu transition wait in the original
            # events (shop opening, MainUI expansion), not a wait for close.
            self.ui_wait_job = None
            self.pending_wait = None
            try:
                self.runtime.resume()
            except (RuntimeError, ValueError) as error:
                self.event_issue = str(error)
                return
            self.drive()

        self.ui_wait_job = self.root.after(delay, poll)

    def advance_button_tip(self):
        if not self.display_request or self.display_request.kind != 'button':
            return
        request = self.display_request
        self.display_request = None
        self.dialogue = None
        if self.runtime.pending is request:
            self.runtime.resume()
        if self.ui_open:
            # The click may have opened the tutorial's next page.
            self.ui_tutorial_active = True
        self.drive()

    def on_canvas_wheel(self, event):
        if self.task_page:
            self.task_page.wheel(event.delta/120, event.x*800/self.WIDTH, event.y*480/self.HEIGHT)
        elif self.battle_ui:
            self.battle_ui.wheel(event.delta/120)

    def task_page_event(self, kind, event):
        if getattr(self, 'task_page', None):
            getattr(self.task_page, kind)(event.x*800/self.WIDTH, event.y*480/self.HEIGHT)

    def click_walk(self, screen_x, screen_y):
        camx, camy = self.camera_origin()
        target = None
        for actor in sorted(self.actors(), key=lambda row: row[3], reverse=True):
            oid, sid, x, y = actor
            if str(oid).startswith(('temp:', 'fx:')):
                continue
            sprite = self.scene_sprite(sid, self.actor_animation(oid, sid))
            if sprite is None:
                continue
            anchor = sprite.info.get('origin', (sprite.width/2, sprite.height))
            left, top = (x-anchor[0])*self.SCALE-camx, (y-anchor[1])*self.SCALE-camy
            px, py = int((screen_x-left)/self.SCALE), int((screen_y-top)/self.SCALE)
            if 0 <= px < sprite.width and 0 <= py < sprite.height and sprite.getpixel((px, py))[3] > 0:
                target = actor
                break
            if str(oid).isdigit() and str(sid).isdigit() and 20000 <= int(sid) < 30000:
                from task_icons import TaskIcons
                resolver = getattr(self, 'task_icons', None)
                if resolver is None or resolver.state is not self.state:
                    resolver = self.task_icons = TaskIcons(self.state)
                icon_id = resolver.for_npc(oid)
                if icon_id:
                    icon = self.data.image(f'TaskIcon/taskIcon{icon_id}.png')
                    width, height = round(icon.width*self.SCALE*.5), round(icon.height*self.SCALE*.5)
                    icon_x = x*self.SCALE-camx-width/2
                    icon_y = top-height+resolver.bob(getattr(self, 'scene_animation_time', 0))*self.SCALE
                    if icon_x <= screen_x <= icon_x+width and icon_y <= screen_y <= icon_y+height:
                        target = actor
                        break
        self.keys.clear()
        if target:
            self.guide.start_click(target[2], target[3], target[0], target[1])
        else:
            self.guide.start_click((screen_x+camx)/self.SCALE, (screen_y+camy)/self.SCALE)

    def start_battle(self, npcid, kind=None):
        if self.battle:
            return False
        if not self.state.pets:
            self.runtime_error = ''
            self.event_issue = '原战斗要求至少一只宠物；当前队伍为空。'
            self.event_notice = self.event_issue
            if self.runtime.running:
                self.runtime.abort('battle-with-empty-party')
            return False
        if not any(p.hp > 0 for p in self.state.pets):
            # A fainted party must not enter a normal battle. Release the
            # original pending fight instead of leaving runtime_error set,
            # which used to lock movement/NPC interaction forever. No
            # victory, reward, healing, or task progress is fabricated.
            self.runtime_error = ''
            self.pending_wait = None
            self.event_issue = ('队伍已全灭，本次挑战未开始。请去治疗或使用复活石复活宠物，'
                                '再回来重新挑战。')
            self.event_notice = self.event_issue
            if self.runtime.running:
                self.runtime.abort('all-pets-fainted')
            self.state.audit.append({'battle': str(npcid), 'aborted': 'all-pets-fainted'})
            return False
        if kind == 'wild' or str(npcid) in self.data.tables.get('VillageEnemy', {}):
            battle = make_wild_battle(self.data.tables, self.state.pets, npcid, self.state.rng)
        elif kind == 'arena':
            progress = ArenaProgress(self.state)
            with self.state.transaction():
                progress.enter(npcid)
                battle = make_arena_battle(self.data.tables, self.state.pets, npcid,
                                           self.state.rng, rank=progress.rank(npcid))
        elif kind == 'infinite_arena':
            progress = InfiniteArenaProgress(self.state)
            with self.state.transaction():
                progress.enter(npcid)
                battle = make_infinite_arena_battle(self.data.tables, self.state.pets,
                                                    npcid, self.state.rng,
                                                    level=progress.level(npcid))
        elif kind == 'budokan':
            progress = BudokanProgress(self.state)
            npc = progress.next_npc(npcid)
            if not npc:
                raise PendingMechanic(f'{progress.gym(npcid)["name"]} 二十场试练已经完成')
            battle = make_budokan_battle(self.data.tables, self.state.pets,
                                         npcid, npc['keyId'], self.state.rng)
        else:
            battle = make_npc_battle(self.data.tables, self.state.pets, npcid, self.state.rng)
        battle.select_initial_player(self.state.active_pet)
        if battle.enemy_active:
            self.state.record_seen_pet(battle.enemy_active.pet.species)
        self.battle, self.battle_ui = battle, BattleUI(self, battle)
        self.event_notice = ''
        battle.source_id = str(npcid)
        self.battle_tips = []
        self.keys.clear()
        self.dialogue = None
        self.event_issue = ''
        self.player_sprite = self.state.sprite_id
        if battle.kind == 'wild':
            self.runtime.notify('fight', type=1)
            self.drive()
        return True

    def finish_battle(self):
        battle = self.battle
        if not battle or not battle.result:
            return
        result = battle.result
        arena_battle = battle.kind == 'arena'
        infinite_battle = battle.kind == 'infinite_arena'
        budokan_battle = battle.kind == 'budokan'
        arena_summary = None
        if result in ('win', 'caught'):
            battle.apply_rewards(self.state)
        if arena_battle:
            arena_summary = ArenaProgress(self.state).finish(
                battle.arena_id, battle.arena_npc_id, result)
            self.arena_summary = arena_summary
            if result == 'win':
                drops = '、'.join(f'{self.data.tables["Item"].get(i, self.data.tables["Money"].get(i, {})).get("name", i)}×{n}'
                                  for i, n in arena_summary['drops']) or '无'
                self.battle_tips.append(
                    f'竞技场排名 {arena_summary["rank_before"]} → {arena_summary["rank_after"]}，'
                    f'称号：{arena_summary["title"]}，奖励：{drops}')
        elif infinite_battle:
            arena_summary = InfiniteArenaProgress(self.state).finish(result, battle.infinite_arena_id)
            self.arena_summary = arena_summary
            if result == 'win':
                self.battle_tips.append(
                    f'无限竞技场第 {arena_summary["level_before"]} 层通过，'
                    f'进入第 {arena_summary["level_after"]} 层，荣誉 +1。')
        elif budokan_battle:
            budokan_summary = BudokanProgress(self.state).finish(
                battle.budokan_id, battle.budokan_npc_id, result)
            self.budokan_summary = budokan_summary
            if result == 'win':
                drops = '、'.join(
                    f'{self.data.tables["Item"].get(i, self.data.tables["Money"].get(i, {})).get("name", i)}×{n}'
                    for i, n in battle.drops) or '无'
                self.battle_tips.append(
                    f'{budokan_summary["npc_name"]} 通过：'
                    f'{budokan_summary["after"]} / {budokan_summary["total"]}，奖励：{drops}')
        if result == 'win':
            self.state.activities['battle_wins'] = int(
                self.state.activities.get('battle_wins', 0))+1
            if any(event.get('type') == 'oneshot' for event in battle.events):
                self.state.activities['oneshot_wins'] = int(
                    self.state.activities.get('oneshot_wins', 0))+1
        applied = dict(self.state.activities.get('status_applies', {}))
        for event in battle.events:
            if event.get('type') == 'state_applied':
                kind = str(event.get('kind'))
                applied[kind] = int(applied.get(kind, 0))+1
        if applied:
            self.state.activities['status_applies'] = applied
        if result == 'caught':
            pet = battle.caught_pet
            land = int(self.data.tables['Pet'][pet.species].get('kind', -1))
            TaskProgress(self.state).update('catch', int(pet.species), land, self.state.map_id)
            DailyTasks(self.state).record('catch')
            self.state.activities['caught_total'] = int(
                self.state.activities.get('caught_total', 0))+1
        elif result == 'win' and battle.kind != 'wild' and not arena_battle and not infinite_battle and not budokan_battle:
            TaskProgress(self.state).update('fight', 2, 1, int(battle.source_id), -1)
            self.state.npc_fights[battle.source_id] = 1
            DailyTasks(self.state).record('fight')
        TaskProgress(self.state).update()
        if battle.kind == 'wild' and result in ('win', 'caught'):
            self.runtime.notify('fightover', type=1, result=1,
                                petid=int(battle.caught_pet.species if battle.caught_pet else battle.enemy_active.pet.species))
        for unit in battle.player:
            unit.pet.hp, unit.pet.energy = unit.hp, unit.energy
            if unit.pet.trial_id and unit.pet.trial_remaining > 0 and (unit.participated or unit is battle.player_active):
                unit.pet.trial_remaining -= 1
        self.state.active_pet = min(battle.player_index, max(0, len(self.state.pets)-1))
        if self.state.pets and self.state.pets[self.state.active_pet].trial_remaining == 0:
            self.state.active_pet = next((i for i, p in enumerate(self.state.pets) if p.hp > 0 and p.trial_remaining != 0), 0)
        self.runtime.battle_result = 'win' if result in ('win', 'caught') else (
            'escape' if result == 'escape' else 'lose')
        self.battle, self.battle_ui = None, None
        self.battle_tips = []
        self.display_request = None
        self.encounter_distance = 0.0
        self.reset_encounter()
        if self.runtime.pending and self.runtime.pending.kind == 'battleover':
            self.runtime.resume(self.runtime.battle_result)
        elif self.runtime.pending and self.runtime.pending.kind == 'wait':
            self.pending_wait = None
            self.runtime.resume()
        self.drive()

    def follow_focus(self):
        # setViewpointCenter @ 0x2d8f50 follows player + (0, tileHeight)
        # in Cocos bottom-origin space; native map coordinates use top origin.
        return self.x, self.y-self.map.th

    def release_story_camera(self):
        # Original eventRunningProcess reenables camera follow at plot end.
        self.camera_focus = self.camera_action = None

    def begin_camera_move(self, parameter):
        target = self.follow_focus() if parameter.get('x', -1) == -1 and parameter.get('y', -1) == -1 else (
            (float(parameter['x'])+.5)*self.map.tw,
            (float(parameter['y'])-.5)*self.map.th)
        def visible_center(point):
            x, y = self.camera_origin(point)
            return [(x+self.WIDTH/2)/self.SCALE, (y+self.HEIGHT/2)/self.SCALE]
        start = visible_center(self.camera_focus or self.follow_focus())
        target = visible_center(target)
        speed = int(parameter.get('speedscale', 1))
        if speed < 0:
            raise ValueError('原镜头指令 speedscale 不能小于零')
        stop = parameter.get('stop') == 1
        if speed == 0:
            self.camera_action = None
            self.camera_focus = target if stop else None
            return
        # setViewpoint @ 0x2d9eb0: MoveTo, DelayTime(.5), moveScreenOver.
        self.camera_focus = start
        self.camera_action = {'start': start, 'target': target,
                              'duration': math.dist(start, target)/self.map.th*.1/speed,
                              'elapsed': 0.0, 'stop': stop}

    def advance_camera(self, seconds):
        action = getattr(self, 'camera_action', None)
        if not action:
            return
        action['elapsed'] += max(0, seconds)
        fraction = min(1, action['elapsed']/action['duration']) if action['duration'] else 1
        self.camera_focus = [a+(b-a)*fraction for a, b in zip(action['start'], action['target'])]
        if action['elapsed'] >= action['duration']+.5:
            self.camera_focus = action['target'] if action['stop'] else None
            self.camera_action = None
            if self.runtime.pending and self.runtime.pending.kind == 'screenmove':
                self.runtime.resume()

    def drive(self):
        face_until = getattr(self, 'story_face_until', 0)
        if face_until:
            if time.monotonic() < face_until:
                return
            self.story_face_until = 0
            if self.runtime.pending and self.runtime.pending.kind == 'face':
                self.runtime.resume()
        fade_until = getattr(self, 'screen_fade_until', 0)
        if fade_until:
            if time.monotonic() < fade_until:
                return
            self.screen_fade_until = 0
            if self.runtime.pending and self.runtime.pending.kind == 'screen':
                self.runtime.resume()
        flash_until = getattr(self, 'flash_until', 0)
        if flash_until:
            if time.monotonic() < flash_until:
                return
            self.flash_until = 0
            if self.runtime.pending and self.runtime.pending.kind == 'screenflash':
                self.runtime.resume()
        if (self.display_request and self.display_request.kind == 'airtalk'
                and time.monotonic() >= getattr(self, 'air_talk_until', float('inf'))):
            self.display_request = self.dialogue = None
            self.runtime.resume()
        if getattr(self, 'camera_action', None):
            return
        if getattr(getattr(self, 'story_motion', None), 'actions', []):
            return
        if self.display_request or self.runtime_error:
            return
        if self.battle and not self.runtime.running:
            return
        if self.pending_wait:
            return
        if self.ui_open and not (getattr(self, 'ui_tutorial_active', False)
                                 or getattr(self, 'ui_story_active', False)):
            # A tutorial page is allowed to advance to its next button/wait
            # request while the page stays open. Other story commands wait
            # until close_ui resumes the original openui request.
            pending = self.runtime.pending
            if not pending or pending.kind not in ('button', 'wait', 'closeui'):
                return
        if time.monotonic() < self.wait_until:
            return
        for _ in range(100):
            try:
                request = self.runtime.next()
                if not request:
                    self.dialogue = None
                    self.runtime.flush_queue()
                    if self.runtime.running:
                        continue
                    return
                if request.kind in ['talk', 'aside', 'airtalk']:
                    if request.kind == 'talk':
                        DailyTasks(self.state).record('talk')
                    self.display_request = request
                    self.dialogue = request.data.get('text') or '\n'.join(request.data.get('texts', []))
                    if request.kind == 'airtalk':
                        # showAirTalk @ 0x39f39c schedules a two-second DelayTime.
                        self.air_talk_until = time.monotonic()+2
                    return
                if request.kind == 'reward':
                    if request.data['items']:
                        self.show_reward(request.data.get('title', '获得奖励'), request.data['items'])
                    else:
                        self.game_tip(request.data['title'])
                    return
                if request.kind == 'button':
                    self.runtime.resume()
                    continue
                if request.kind == 'tapscreen':
                    self.display_request = request
                    self.dialogue = request.data.get('text') or '点击继续'
                    return
                if request.kind == 'fight':
                    parameters = request.data.get('parameters', {})
                    npcid = parameters.get('npcid')
                    if npcid is None:
                        raise PendingMechanic('原战斗指令没有 npcid，不能改用虚构对手')
                    if parameters.get('confirm'):
                        row = self.data.tables['NpcFight'].get(str(npcid), {})
                        self.confirm_battle(request, npcid, int(parameters.get('type', 0) or 0))
                        return
                    fight_type = int(parameters.get('type', 0) or 0)
                    if not self.start_battle(npcid, kind={3: 'arena', 4: 'budokan', 5: 'infinite_arena'}.get(fight_type)):
                        return
                    self.runtime.resume('start')
                    self.drive()
                    return
                if request.kind == 'battleover':
                    if not self.battle:
                        raise PendingMechanic('缺少实际战斗结果，不能代填胜负；请读取战斗前存档')
                    return
                if request.kind == 'openui':
                    self.open_ui(request)
                    # Ordinary pages wait for the player to close them.
                    # Some original map scenes talk/scroll while the map is
                    # open, then explicitly close it with auto=1.
                    for step in self.runtime.sequence[self.runtime.index+1:]:
                        if step['type'] == 'openui':
                            break
                        if step['type'] == 'closeui':
                            if step.get('parameters', {}).get('auto') == 1:
                                self.ui_story_active = True
                                self.runtime.resume()
                                break
                            break
                    if self.ui_story_active:
                        continue
                    return
                if request.kind == 'closeui':
                    self.close_ui()
                    return
                if request.kind == 'accepttask':
                    self.accept_task_ui(request)
                    return
                if request.kind == 'costtaskitem':
                    if self.begin_task_handover(request):
                        continue
                    return
                if request.kind == 'wait':
                    parameters = request.data.get('parameters', {})
                    wait_type = int(parameters.get('type', 0) or 0)
                    if self.battle:
                        self.pending_wait = request
                        return
                    if wait_type == 2 and self.ui_open:
                        self.pending_wait = request
                        self._schedule_ui_wait(request)
                        return
                    if wait_type == 2:
                        self.pending_wait = request
                        self._schedule_ui_wait(request)
                        return
                    if wait_type == 3:
                        self.pending_wait = request
                        self.event_issue = '等待原版场景障碍/骑乘交互；点击继续可恢复剧情'
                        return
                    self.runtime.resume()
                    continue
                self.apply_visual(request)
                if (self.camera_action or getattr(self, 'screen_fade_until', 0)
                        or getattr(self, 'story_face_until', 0)
                        or getattr(self, 'flash_until', 0)
                        or getattr(getattr(self, 'story_motion', None), 'actions', [])):
                    return
                self.runtime.resume()
                self.player_sprite = self.state.sprite_id
            except (PendingMechanic, NotImplementedError, ValueError, KeyError) as error:
                self.runtime_error = f'{self.runtime.file}：{error}'
                self.state.audit.append({'event': self.runtime.file, 'index': self.runtime.index, 'pending': str(error)})
                recorder = getattr(self, 'record_callback_error', None)
                if recorder:
                    recorder(type(error), error, error.__traceback__)
                return

    def battle_action_complete(self):
        if self.battle and self.battle.enemy_active:
            self.state.record_seen_pet(self.battle.enemy_active.pet.species)
        if self.pending_wait and self.runtime.pending is self.pending_wait:
            self.pending_wait = None
            self.runtime.resume()
        self.drive()

    def process_player_areas(self, force=False):
        """areaProcess @ 0x2e4934: plot notification, then type-1 task event.

        PlotEventManager::process @ 0x2f7958 ignores new triggers while its
        running flag is set. Task counters still receive the area event.
        """
        tile = (self.map_id, int(self.x//self.map.tw), int(self.y//self.map.th))
        if not force and tile == getattr(self, '_processed_area_tile', None):
            return
        self._processed_area_tile = tile
        x, y = (tile[1]+.5)*self.map.tw, (tile[2]+.5)*self.map.th
        self.inside_areas = set()
        from area_order import native_area_order
        stamp = (id(self.map), id(self.map.objects), len(self.map.objects))
        if getattr(self, '_area_order_stamp', None) != stamp:
            self._area_order_stamp = stamp
            self._ordered_areas = native_area_order(self.map.objects)
        for obj in self._ordered_areas:
            left, top = float(obj.get('x', 0)), float(obj.get('y', 0))
            width, height = float(obj.get('width', 64)), float(obj.get('height', 64))
            if not (left <= x < left+width and top <= y < top+height):
                continue
            area = int(obj['name'])
            self.inside_areas = {str(area)}
            if not self.runtime.running:
                started = self.runtime.notify('toarea', area=area)
                task = self.state.tables['MainTask'].get(str(self.state.main_task), {})
                if (not started and self.state.main_state == 4 and int(task.get('conditionType', 0)) == 1
                        and area in numbers(task.get('conditions', '0'))):
                    # An old save may have counted this area while its plot
                    # was masked. Retry the original pre-count trigger here,
                    # preserving actual ready state and all task counters.
                    self.state.main_state = 3
                    try:
                        self.runtime.notify('toarea', area=area)
                    finally:
                        self.state.main_state = 4
            self.advance_main_condition('area', area)
            npc_id = obj.get('props', {}).get('npcId')
            if npc_id and not self.runtime.running and not self.ui_open:
                self.interact(str(npc_id))
            # getAreaSpriteAtTileCoord returns one matching native area.
            return

    def tick(self):
        self._frame_started = time.perf_counter()
        now = time.monotonic()
        if getattr(self, 'opening', None):
            self._play_clock = now
            self.last_time = now
            self.frame = self.make_frame()
            self.viewport.present(self.frame)
            self.root.after(33, self.tick)
            return
        if hasattr(self, 'audio'):
            for kind, flag in [('music', 'music_enabled'), ('effect', 'effects_enabled')]:
                enabled = self.state.presentation.get(kind+'_enabled', True)
                if getattr(self.audio, flag) != enabled:
                    self.audio.set_enabled(kind, enabled)
            result = self.battle.result if self.battle and not self.battle_ui.anim else None
            result_music = {'win': '401', 'lose': '402', 'caught': '403'}.get(result)
            self.audio.music(result_music or (self.battle.bgm if self.battle and str(self.battle.bgm) != '0' else
                                 '301' if self.battle else self.map.info.get('bgmId', '0')), loop=not bool(result_music))
        elapsed = max(0.0, now-self._play_clock)
        self._play_clock = now
        if not self.booting and self.ui_open and self.ui_window and self.ui_window.winfo_exists():
            # The modal owns a captured scene and its own animation timer.
            # Do not redraw the entire map behind that immutable scene.
            self.last_time = now
            self.state.activities['play_seconds'] = float(self.state.activities.get('play_seconds', 0))+elapsed
            if self.ui_story_active:
                self.advance_camera(elapsed)
                self.drive()
                self.paint_modal_story()
            self.root.after(33, self.tick)
            return
        if not self.booting:
            self.scene_animation_time += elapsed
            self.player_walking = False
            self.advance_camera(elapsed)
            if not self.runtime_error:
                try:
                    self.story_motion.advance(elapsed)
                    if self.npc_motion:
                        self.npc_motion.advance(elapsed)
                except (PendingMechanic, ValueError, KeyError) as error:
                    self.runtime_error = f'{self.runtime.file}：{error}'
                    recorder = getattr(self, 'record_callback_error', None)
                    if recorder:
                        recorder(type(error), error, error.__traceback__)
            self.state.activities['play_seconds'] = (
                float(self.state.activities.get('play_seconds', 0))+elapsed)
        if self.battle and self.battle_ui:
            self.battle_ui.advance(seconds=elapsed)
        if getattr(self, 'treasure_search_fx', None):
            self.treasure_search_fx['age'] += elapsed
            if self.treasure_search_fx['age'] >= 2:
                self.treasure_search_fx = None
        if getattr(self, 'chest_fx', None):
            self.chest_fx['age'] += 1
            if self.chest_fx['age'] >= 26:
                self.chest_fx = None
        if getattr(self, 'obstacle_fx', None):
            self.obstacle_fx['age'] += 1
            if self.obstacle_fx['age'] >= 22:
                self.obstacle_fx = None
        old_map, old_x, old_y = self.map_id, self.x, self.y
        if not self.booting:
            TaskProgress(self.state).update()
            self.drive()
            self.steps = [1] if self.runtime.running or self.runtime_error or self.ui_open else []
            self.guide.step(elapsed)
        super().tick()
        if self.booting:
            return
        if not self.battle and self.map_id == old_map:
            self.encounter_distance += abs(self.x-old_x) + abs(self.y-old_y)
            if self.check_encounter():
                self.steps = [1]
                self.status.set('野外遭遇！')
                return
        if self.battle:
            self.steps = [1]
            message = self.battle.messages[-1] if self.battle.messages else ''
            self.status.set('点击我方宠物打开补给/换宠，点击对方宠物打开技能/捕捉 | '+message)
            return
        self.state.map_id, self.state.x, self.state.y = self.map_id, self.x, self.y
        if not any(a['kind'] == 1 for a in self.story_motion.actions):
            self.process_player_areas()
        self.event_issue = self.runtime_error or self.event_notice
        guide_note = ''
        if self.guide.target:
            guide_note = f' | 指引：{self.guide.target.label}'
            if self.guide.active:
                guide_note += f'（自动前往，剩余 {max(0, len(self.guide.route)-1)} 张地图）'
            elif self.guide.message:
                guide_note += f'（{self.guide.message}）'
        self.status.set(self.runtime_error or ('方向键/WASD移动 · 空格/E对话 · F5保存 · F9读取 · G指引'
                                               ' | 原剧情状态机、战斗核心与原版战斗UI已接入' + guide_note))

    def paint_modal_story(self):
        if not self.ui_story_active or not self.ui_open or not self.original_page:
            return
        page = self.original_page
        frame = getattr(page, 'display_frame', page.layer).copy()
        if self.dialogue:
            name, content = (self.dialogue.split(':', 1) if ':' in self.dialogue else ('', self.dialogue))
            side = 'left' if name == self.state.player_name else 'right'
            portrait = next((row.get('icon') for row in self.data.tables['Npc'].values()
                             if row.get('name') == name), None)
            if portrait:
                art = self.data.image('res/UI/HeadIcon/'+portrait)
                frame.alpha_composite(art, (0 if side == 'left' else 800-art.width, 480-art.height))
            frame.alpha_composite(self.cocos_ui.render('DialogUI', (800, 480),
                text={side+'Name_Text': name, side+'Dialog_Text': content},
                visible={'leftDialog_Panel': side == 'left', 'rightDialog_Panel': side == 'right'}))
        self.ui_base_layer = frame
        self.ui_art_label.set_layer(frame)

    def _decorate_ui_tutorial(self, frame):
        request = self.display_request
        if not request or request.kind != 'button' or not self.ui_open:
            return frame
        key = request.data.get('nodekey', '')
        name = self._ui_tutorial_target(key)
        if not name:
            return frame
        rect = self.ui_hits.get(name)
        if not rect:
            return frame
        frame = frame.copy()
        draw = ImageDraw.Draw(frame, 'RGBA')
        issued = request.data.get('text') or request.data.get('nodekey', '')
        # The original TeachUI arrow/hand assets remain the pointing artwork;
        # this banner only carries the event's own tutorial sentence.
        arrow = self.data.image('UI/teach_arrow.png')
        arrow = arrow.resize((max(1, round(arrow.width*.65)), max(1, round(arrow.height*.65))),
                             Image.Resampling.LANCZOS)
        ax = round((rect[0]+rect[2])/2-arrow.width/2)
        ay = max(0, round(rect[1]-arrow.height-4))
        frame.alpha_composite(arrow, (ax, ay))
        if issued:
            font = self.cocos_ui.font('', 17)
            box = draw.textbbox((0, 0), issued, font=font)
            width = min(720, box[2]-box[0]+34)
            left = max(8, (800-width)//2)
            draw.rounded_rectangle((left, 438, left+width, 474), radius=8,
                                   fill=(20, 24, 28, 220), outline=(255, 226, 120, 230), width=2)
            draw.text((400, 456), issued, font=font, fill='#fff4cf', anchor='mm')
        return frame

    def _draw_button_tutorial(self, frame):
        request = self.display_request
        if not request or request.kind != 'button':
            return
        key = request.data.get('nodekey', '')
        rect = self.scene_ui.hits.get(key)
        if not rect:
            return
        text = request.data.get('text', '')
        font_size = 30
        width = min(700, math.ceil(self.cocos_ui.font('', font_size).getlength(text))+4)
        height = max(42, math.ceil(self.cocos_ui.font('', font_size).getlength(text)/width)*33)
        layer = self.cocos_ui.render('TipsUiNode', (self.WIDTH, self.HEIGHT),
                    text={'tip_Text': text}, sizes={'bg_Image': (width+32, height+20), 'tip_Text': (width, height)},
                    positions={'Node': (400, 390), 'tip_Text': ((width+32)/2, (height+20)/2)})
        frame.alpha_composite(layer)
        marker = self.data.armature('dianji', 'Animation1', int(self.scene_animation_time*60))
        if marker is not None:
            origin = marker.info.get('origin', (marker.width/2, marker.height/2))
            frame.alpha_composite(marker, (round((rect[0]+rect[2])/2-origin[0]), round((rect[1]+rect[3])/2-origin[1])))

    def draw_story_face_icons(self, frame):
        icons = getattr(self, 'story_face_icons', {})
        if not icons:
            return
        camera_x, camera_y = self.camera_origin()
        for actor, (face, started) in list(icons.items()):
            age = time.monotonic()-started
            if age >= 2:
                del icons[actor]
                continue
            try:
                x, y = self.story_motion.position(*actor)
            except PendingMechanic:
                continue
            art = self.data.armature('face', str(face), int(age*60))
            if art is not None:
                frame.alpha_composite(art, (round(x*self.SCALE-camera_x-art.width/2),
                                            round((y-64)*self.SCALE-camera_y-art.height)))

    def draw_air_talk(self, frame, request):
        camera_x, camera_y = self.camera_origin()
        actors = {str(oid): (x, y) for oid, _, x, y in self.actors()}
        texts = request.data.get('texts', [])
        rows = request.data.get('parameters', [])
        bubbles = {}
        for row in rows if isinstance(rows, list) else [rows]:
            kind, identifier = int(row.get('spritetype', 2)), str(row.get('spriteid', 0))
            point = (self.x, self.y) if kind == 1 else actors.get(('temp:' if kind == 7 else '')+identifier)
            index = int(row.get('index', 0))
            if point is None or not 0 <= index < len(texts):
                continue
            x, y = point[0]*self.SCALE-camera_x, point[1]*self.SCALE-camera_y
            if index not in bubbles:
                width, height = round(160*self.WIDTH/800), round(92*self.HEIGHT/480)
                bubbles[index] = self.cocos_ui.render('BubbleDialogNode', (width,height),
                    text={'dialog_Text': texts[index]}, canvas_size=(160,92), offset=(width/2,height/2))
            bubble = bubbles[index]
            left = round(max(0, min(x-bubble.width/2, self.WIDTH-bubble.width)))
            top = round(max(0, min(y-60*self.SCALE-bubble.height, self.HEIGHT-bubble.height)))
            frame.alpha_composite(bubble, (left,top))

    def draw_map_name(self, frame):
        now = time.monotonic()
        if self.map_name_started is None:
            self.map_name_started = now
        age = now-self.map_name_started
        if age >= 2.5:
            return
        key = self.map.info['name'], self.WIDTH, self.HEIGHT
        if getattr(self, '_map_name_key', None) != key:
            width, height = round(228*self.WIDTH/800), round(60*self.HEIGHT/480)
            self._map_name_art = self.cocos_ui.render('MapNameNode', (width, height),
                text={'name_Text': key[0]}, canvas_size=(228, 60), offset=(width/2, height/2))
            self._map_name_key = key
        art = self._map_name_art
        if age > 2:
            art = Image.blend(art, Image.new('RGBA', art.size), max(0, (age-2)*2))
        frame.alpha_composite(art, ((self.WIDTH-art.width)//2, round(24*self.HEIGHT/480-art.height/2)))

    def make_frame(self):
        if getattr(self, 'opening', None):
            clips, index, started = self.opening
            begin, end = clips[index]
            offset = int((time.monotonic()-started)*60)
            position = begin + min(offset, end-begin)
            if index == len(clips)-2 and offset >= end-begin:
                loop_start, loop_end = clips[-1]
                position = loop_start + (offset-(end-begin)) % (loop_end-loop_start)
            layer = self.cocos_ui.render('OpeningUI', (self.WIDTH, self.HEIGHT), timeline_frame=position)
            self._opening_skip = self.cocos_ui.buttons.get('skip_Button')
            frame = Image.new('RGBA', layer.size, 'black')
            frame.alpha_composite(layer)
            return frame
        if self.battle and self.battle_ui:
            return self.battle_ui.render()
        original_dialogue = self.dialogue
        self.dialogue = None
        try:
            frame = super().make_frame()
        finally:
            self.dialogue = original_dialogue
        self.draw_exit_markers(frame)
        black = getattr(self, 'screen_black', False)
        remaining = max(0, getattr(self, 'screen_fade_until', 0)-time.monotonic())
        opacity = min(1, remaining/.5)
        if black:
            opacity = 1-opacity
        if self.main_ui_visible and opacity < 1:
            self.scene_ui.render(frame)
        if opacity:
            frame = Image.blend(frame, Image.new('RGBA', frame.size, 'black'), opacity)
        else:
            self.draw_map_name(frame)
            self.draw_story_face_icons(frame)
        if original_dialogue is None:
            self._draw_chest_fx(frame)
            self._draw_obstacle_fx(frame)
            self._draw_treasure_search(frame)
        request = self.display_request
        if request and request.kind == 'airtalk':
            self.draw_air_talk(frame, request)
        elif request and request.kind == 'aside':
            frame.alpha_composite(self.cocos_ui.render('AsideUI', (self.WIDTH, self.HEIGHT),
                                  text={'aside_Text': original_dialogue or ''}))
        elif original_dialogue is not None:
            name, sep, content = original_dialogue.replace('：', ':', 1).partition(':')
            if not sep:
                name, content = '', original_dialogue
            is_player = name in ['尼尔', '皮尔']
            portrait = next((r['icon'] for r in self.data.tables['Npc'].values() if r['name'] == name), None)
            if name == '宠物护士':
                # The generic pink-haired nurse (village npc9) shares the
                # recovered pink-haired head portrait used by the shop clerk.
                portrait = self.data.tables['Npc']['13']['icon']
            if portrait:
                image = self.data.image('res/UI/HeadIcon/'+portrait).copy()
                size = (round(image.width*self.WIDTH/800), round(image.height*self.HEIGHT/480))
                image = image.resize(size, Image.Resampling.LANCZOS)
                frame.alpha_composite(image, (0 if is_player else self.WIDTH-image.width, self.HEIGHT-image.height))
            side = 'left' if is_player else 'right'
            overlay = self.cocos_ui.render('DialogUI', (self.WIDTH, self.HEIGHT),
                text={side+'Name_Text': name, side+'Dialog_Text': content},
                visible={'leftDialog_Panel': is_player, 'rightDialog_Panel': not is_player})
            frame.alpha_composite(overlay)
        else:
            self.draw_guide(frame)
            self._draw_button_tutorial(frame)
        flash_remaining = getattr(self, 'flash_until', 0)-time.monotonic()
        if flash_remaining > 0:
            frame = Image.blend(frame, Image.new('RGBA', frame.size, 'white'),
                                min(1, flash_remaining/.2)*(150/255))
        if getattr(self, 'task_page', None):
            frame.alpha_composite(self.task_page.render().resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS))
        self.scene_ui.render_tip(frame)
        return frame

    def draw_guide(self, frame):
        from task_guide import TaskGuide
        if not hasattr(self, 'task_guide'):
            self.task_guide = TaskGuide(self)
        self.task_guide.draw(frame)

    def save_ui(self):
        if self.booting:
            return
        if self.battle:
            self.event_issue = '战斗中不能保存，请先结束战斗。'
            return
        if self.ui_open:
            return
        self.open_ui(Request('openui', 'save-button', 0,
                            {'parameters': {'uiid': 14}}))

    def autosave(self):
        self.autosave_job = None
        if not self.booting and not self.opening and not self.battle and not self.runtime_error:
            self.save()
        self.autosave_job = self.root.after(30000, self.autosave)

    def close_game(self):
        # Battle snapshots are not implemented: keep the pre-battle save.
        if not self.opening and not self.battle and not self.save():
            self.game_tip(self.event_issue)
            return
        self.root.destroy()

    def save(self):
        if self.booting:
            return False
        if self.battle:
            self.event_issue = '战斗中存档尚未接入原版战斗快照，未写入不一致的进度。'
            return False
        try:
            self.state.map_id, self.state.x, self.state.y = self.map_id, self.x, self.y
            self.state.presentation = {
                **self.state.presentation,
                'face': self.face, 'player_visible': self.player_visible,
                'player_visibility_map': self.map_id,
                'sprite_collision_version': 2,
                'obstacle_coordinates_version': 2,
                'camera_focus': self.camera_focus, 'main_ui_visible': self.main_ui_visible,
                'camera_action': self.camera_action,
                'story_motion_actions': self.story_motion.actions if getattr(self, 'story_motion', None) else [],
                'story_motion_faces': self.story_motion.faces if getattr(self, 'story_motion', None) else {},
                'npc_motion': self.npc_motion.snapshot() if getattr(self, 'npc_motion', None) else None,
                'scene_animation_time': getattr(self, 'scene_animation_time', 0.0),
                'teach_nodes': self.teach_nodes, 'screen_black': getattr(self, 'screen_black', False),
                'screen_mask_map': self.map_id,
                'encounter_distance': self.encounter_distance,
                'encounter_threshold': self.encounter_threshold,
            }
            self.runtime.persist()
            self.state.activities['save_total'] = int(
                self.state.activities.get('save_total', 0))+1
            self.state.save(self.save_path)
        except (OSError, ValueError, TypeError) as error:
            self.event_issue = f'保存失败：{error}'
            return False
        self.event_issue = f'已保存到本机用户存档：{self.save_path}'
        if self.ui_info:
            self.ui_info.set(self.event_issue)
        return True

    def restore(self):
        if self.battle:
            self.event_issue = '战斗中暂不支持读取存档，请在战斗结束后读取。'
            return False
        if not self.save_path.exists():
            self.event_issue = '还没有原生移植存档。'
            return False
        try:
            state = GameState.load(self.data.tables, self.save_path)
            from npc_visibility import migrate
            migrate(state)
            self.repair_legacy_obstacle_coordinates(state)
            runtime = EventRuntime(self.data, state)
            runtime.on_finish = self.release_story_camera
            runtime.present_rewards = True
            TaskProgress(state).update()
            runtime.restore(state.pending_runtime)
            self.close_transient_ui()
            self.state, self.runtime = state, runtime
            self.runtime.play_sound = self.audio.effect
            self.guide.rebind(state)
            # Loading the map initializes a fresh encounter, consuming RNG.
            # Restore the saved RNG as well as its existing encounter below.
            random_state = state.rng.getstate()
            self.load_map(state.map_id, state.x, state.y)
            state.rng.setstate(random_state)
            self.runtime_error, self.display_request, self.dialogue = '', None, None
            self.pending_wait, self.wait_until = None, 0
            self.camera_focus, self.screen_black, self.flash_until = None, False, 0
            self.camera_action = None
            self.player_visible, self.main_ui_visible = True, True
            self.teach_nodes, self.battle_tips = [], []
            for key in ('face', 'player_visible', 'camera_focus', 'main_ui_visible',
                        'teach_nodes', 'screen_black', 'encounter_distance', 'encounter_threshold',
                        'camera_action', 'scene_animation_time'):
                if key in state.presentation:
                    setattr(self, key, state.presentation[key])
            self.keys.clear()
            if not runtime.running:
                self.release_story_camera()
            if 'screen_mask_map' not in state.presentation and self.screen_black:
                # Old builds carried the previous map's mask into new plots.
                self.screen_black = False
                for step in runtime.sequence[:runtime.index]:
                    if step['type'] in ('screenclose', 'tomap', 'screen'):
                        self.screen_black = (step['type'] == 'screenclose' or
                            (step['type'] == 'screen' and int(step.get('parameters', {}).get('type', 0)) == 0))
            self.teach_nodes = []
            self.state.trial_ride = 0
            self.main_ui_visible = True
            self.player_sprite = state.sprite_id
            self.repair_starter_save_position()
            self.repair_legacy_player_visibility()
            self.story_motion = StoryMotion(self)
            self.story_motion.actions = state.presentation.get('story_motion_actions', [])
            self.story_motion.faces = state.presentation.get('story_motion_faces', {})
            self.npc_motion = NpcMotion(self)
            self.npc_motion.reset()
            self.npc_motion.restore(state.presentation.get('npc_motion'))
            self.repair_legacy_sprite_collision()
            self.repair_legacy_sunshine_arrival()
            self.repair_legacy_cg_chase()
            self._play_clock = time.monotonic()
            self.drive()
            return True
        except (ValueError, KeyError, OSError) as error:
            self.game_tip(str(error))
            return False

    def repair_legacy_cg_chase(self):
        pending = self.runtime.pending
        if (self.map_id != 507 or not pending or pending.event != 'pEvent507001.json'
                or pending.kind != 'toplace' or pending.step != 3 or self.story_motion.actions):
            return
        companion = self.state.temp_npcs.get('1')
        if (not companion or companion['map'] != self.map_id or companion.get('pspace') != 1
                or (companion['x'], companion['y']) != (-self.map.tw/2, self.map.th/2)):
            return
        # The preceding step has already put the player in position. Restore
        # the companion to the adjacent slot this pending walk was meant to reach.
        companion['x'], companion['y'] = destination(
            pending.data['parameters'], (self.x, self.y), self.face, (self.map.tw, self.map.th))

    def repair_legacy_sunshine_arrival(self):
        # Old request_map advanced task 14 before checking the town plot's
        # state-3 trigger. Resume that exact missed arrival, keeping its actual
        # counter and letting the original script submit/grant just once.
        if (self.map_id != 115 or self.state.main_task != 14 or self.state.main_state != 4
                or self.runtime.running or self.story_motion.actions
                or self.state.events.get('115001', 0)
                or self.state.events.get('5901002', 0) != 1):
            return
        trigger = next(row for row in self.runtime.triggers if row['id'] == 115001)
        self.runtime.start('pEvent115001.json', trigger)
        self.state.audit.append({'repair': 'sunshine-arrival-before-task-ready', 'event': 115001})

    def repair_legacy_obstacle_coordinates(self, state):
        if int(state.presentation.get('obstacle_coordinates_version', 0)) >= 2:
            return
        migrated = []
        for entry in state.removed_obstacles:
            world = self.data.load_map(entry[0])
            for obj in world.objects:
                if obj.get('group') != 'spriteTileLayer' or not obj.get('gid'):
                    continue
                kind = int(world.tile_properties(int(obj['gid'])).get('obsType', 0))
                old = (int(float(obj['x'])//world.tw), int(float(obj['y'])//world.th))
                if kind and old == (int(entry[1]), int(entry[2])) and (len(entry) < 4 or kind == int(entry[3])):
                    before = list(entry)
                    entry[2] = int((float(obj['y'])-world.th/2)//world.th)
                    if before != entry:
                        migrated.append({'before': before, 'after': list(entry)})
                    break
        state.presentation['obstacle_coordinates_version'] = 2
        if migrated:
            state.audit.append({'repair': 'legacy-obstacle-half-tile-origin', 'entries': migrated})

    def repair_starter_save_position(self):
        # Observed old save: the selected-starter plot in the 21x20 lab has
        # x=1376 (tile 21, outside the map) and a stale hidden-player flag.
        # None of these three original scripts hide/move the player. Limit
        # migration to that exact story phase; prologue off-map motion is valid.
        if (self.map_id != 5801 or self.state.main_task != 3 or self.state.main_state != 4
                or not self.state.starter_id or self.runtime.file not in (
                    '', 'pEvent5801002.json', 'pEvent5801003.json', 'pEvent5801004.json')
                or getattr(self, 'screen_black', False)):
            return
        for step in self.runtime.sequence[:self.runtime.index+1]:
            if step['type'] == 'spritevisible':
                rows = step.get('parameters', {})
                if any(p.get('spritetype') == 1 and not p.get('visible', 1)
                       for p in (rows if isinstance(rows, list) else [rows])):
                    return
        before = [self.x, self.y, self.player_visible]
        self.player_visible = True
        world = self.map
        if not (0 <= self.x < world.width*world.tw and 0 <= self.y < world.height*world.th):
            mounts = Mounts(self.state)
            occupied = {(int(a[2]//world.tw), int(a[3]//world.th)) for a in self.actors()}
            candidates = [((tx+.5)*world.tw, (ty+.5)*world.th)
                          for ty in range(world.height) for tx in range(world.width)
                          if (tx, ty) not in occupied and
                          not world.blocked((tx+.5)*world.tw, (ty+.5)*world.th, mounts)]
            if candidates:
                self.x, self.y = min(candidates, key=lambda p: (p[0]-self.x)**2+(p[1]-self.y)**2)
                self.state.x, self.state.y = self.x, self.y
        if before != [self.x, self.y, self.player_visible]:
            self.state.audit.append({'repair': 'starter-save-outside-lab-or-hidden',
                                     'before': before, 'after': [self.x, self.y, self.player_visible]})

    def repair_legacy_player_visibility(self):
        # Confirmed broken save: map 101 / pEvent101001, player flag false,
        # despite no player-hide instruction in this original arrival plot.
        presentation = self.state.presentation
        if ('player_visibility_map' in presentation or self.player_visible
                or self.map_id != 101 or not 1 <= self.state.main_task <= 6):
            return
        for step in self.runtime.sequence[:self.runtime.index+1]:
            if step['type'] != 'spritevisible':
                continue
            rows = step.get('parameters', {})
            for row in rows if isinstance(rows, list) else [rows]:
                if row.get('spritetype') == 1 and not row.get('visible', 1):
                    return
        self.player_visible = True
        self.state.audit.append({'repair': 'legacy-hidden-player-in-101-arrival',
                                 'map': self.map_id, 'event': self.runtime.file})

    def repair_legacy_sprite_collision(self):
        if (self.runtime.running or getattr(self.story_motion, 'actions', [])
                or not hasattr(self.map, 'sprite_blocked')):
            return
        mounts = Mounts(self.state)
        obstacle = self.map.obstacle_at(self.x, self.y)
        obstacle_overlap = bool(obstacle and not mounts.can_fly(int(self.map.info['mapType'])))
        sprite_overlap = (int(self.state.presentation.get('sprite_collision_version', 0)) < 2
                          and self.map.sprite_blocked(self.x, self.y, mounts))
        if not (obstacle_overlap or sprite_overlap):
            return
        origin = [self.x, self.y]
        tx, ty = int(self.x//self.map.tw), int(self.y//self.map.th)
        from collections import deque
        queue, visited = deque([(tx, ty)]), {(tx, ty)}
        while queue:
            x, y = queue.popleft()
            px, py = (x+.5)*self.map.tw, (y+.5)*self.map.th
            if not self.map.blocked(px, py, mounts):
                self.x, self.y = px, py
                self.state.x, self.state.y = px, py
                mounts.enter(self.map.terrain_at(px, py), int(self.map.info['mapType']))
                self.state.audit.append({'repair': ('legacy-player-inside-obstacle' if obstacle_overlap
                                                    else 'legacy-player-inside-sprite-mask'),
                                         'map': self.map_id, 'before': origin, 'after': [px, py]})
                return
            for neighbor in ((x, y+1), (x-1, y), (x+1, y), (x, y-1)):
                if (neighbor not in visited and 0 <= neighbor[0] < self.map.width
                        and 0 <= neighbor[1] < self.map.height):
                    visited.add(neighbor)
                    queue.append(neighbor)

    def close_transient_ui(self):
        self.ui_story_active = False
        lottery = getattr(self, 'lottery_animation', None)
        if lottery is not None:
            lottery.close()
            self.lottery_animation = None
        self.task_page = None
        # Loading must not acknowledge an old event through close_ui().
        if self.ui_window and self.ui_window.winfo_exists():
            job = getattr(self, 'ui_effect_job', None)
            if job:
                self.ui_window.after_cancel(job)
            self.ui_window.destroy()
        self.ui_effect_job = None
        self.original_page = None
        self.page_wheel = None
        self.ui_window, self.ui_open = None, False

    def treasure_ui(self):
        if self.battle or self.runtime.running or self.ui_open:
            return
        from event_runtime import Request
        self.open_ui(Request('openui', 'treasure-menu', 1,
                             {'parameters': {'uiid': 37}}))

    def running_pet_ui(self):
        if self.battle or self.runtime.running or self.ui_open:
            return
        from event_runtime import Request
        self.open_ui(Request('openui', 'running-pet', 1,
                             {'parameters': {'uiid': 39}}))

    def login_ui(self):
        if self.battle or self.runtime.running or self.ui_open:
            return
        from event_runtime import Request
        self.open_ui(Request('openui', 'continuous-login', 1,
                             {'parameters': {'uiid': 12}}))

    def daily_ui(self):
        if self.battle or self.runtime.running or self.ui_open:
            return
        from event_runtime import Request
        self.open_ui(Request('openui', 'daily-task', 1,
                             {'parameters': {'uiid': 44, 'page': 'daily'}}))

    def achievements_ui(self):
        if self.battle or self.runtime.running or self.ui_open:
            return
        from event_runtime import Request
        self.open_ui(Request('openui', 'achievement-list', 1,
                             {'parameters': {'uiid': 45}}))

    def listing(self, title, content):
        win = GameOverlay(self)
        win.title(title)
        box = tk.Text(win, width=68, height=25, wrap='word', font=('Microsoft YaHei UI', 11))
        box.pack(fill='both', expand=True)
        box.insert('1.0', content)
        box.config(state='disabled')
        return win

    def game_tip(self, text):
        if self.ui_open and getattr(self, 'original_page', None) is not None:
            self._page_tip(text, self.original_page.publish)
        else:
            self.open_ui(Request('openui', 'message', 0, {'parameters': {'uiid': 51, 'text': text}}))

    def show_reward(self, title, items):
        """Open the original GetItemUI for a real reward list."""
        if not items:
            return
        if self.ui_open:
            if getattr(self, 'original_page', None) is not None:
                self.reward_overlay(items, self.original_page.publish, title)
                return
            if getattr(self, 'task_page', None) is not None:
                self.open_ui(Request('openui', 'task-reward', 1, {'parameters': {
                    'uiid': 49, 'items': list(items), 'title': title, 'back_task': True}}))
                return
            saved = {key: getattr(self, key, None) for key in (
                'ui_base_layer', 'ui_hits', 'ui_buttons', 'ui_rects', 'ui_button_text',
                'ui_actions', 'ui_render_args', 'original_page', 'page_wheel')}
            body = getattr(self, 'ui_body', None)
            packing = body.pack_info() if body is not None and body.winfo_manager() == 'pack' else None
            if packing:
                body.pack_forget()
            def restore_panel():
                self.__dict__.update(saved)
                self._paint_hover()
                if packing:
                    body.pack(**packing)
            self.reward_overlay(items, restore_panel, title)
            return
        self.open_ui(Request('openui', 'get-item', 1, {
            'parameters': {'uiid': 49, 'title': title, 'items': list(items)}}))

    def _get_item_body(self, body, info):
        body.pack_forget()
        back = (lambda: self.open_ui(Request('openui', 'task', 1, {'parameters': {
            'uiid': 44, 'page': 'daily'}}))) if self.ui_parameters.get('back_task') else None
        self.reward_overlay(self.ui_parameters.get('items', []), back, title=self.ui_parameters.get('title', '获得物品'), underlay=False)

    def _legacy_get_item_body(self, body, info):
        parameters = self.ui_parameters
        title = str(parameters.get('title', '获得物品'))
        items = list(parameters.get('items', []))
        body.pack_forget()
        scroll = [0]

        def resolve(key):
            for table in ('Item', 'Pet', 'Money'):
                row = self.data.tables.get(table, {}).get(str(key))
                if row:
                    return table, row
            return '', {}

        def icon_of(table, row):
            if table == 'Item':
                return f'ItemIcon/{row.get("texture", "")}'
            if table == 'Pet':
                return f'PetHead/head_{row.get("filePath", "")}.png'
            return 'UI/' + row.get('littleIconTexture', 'money_little_icon_gold.png')

        def paint():
            layer = self.cocos_ui.render('GetItemUI', (800, 480),
                                         {'title_Text': title})
            base_hits = dict(self.cocos_ui.hits)
            base_buttons = dict(self.cocos_ui.buttons)
            base_rects = dict(self.cocos_ui.rects)
            base_text = dict(self.cocos_ui.button_text)
            area = (base_rects.get('item_ListView')
                    or base_hits.get('item_ListView'))
            if area:
                visible = items[scroll[0]:scroll[0]+2]
                for slot, (key, count) in enumerate(visible):
                    table, row = resolve(key)
                    card = self.render_component('GetItemUIItemUI', (128, 167), {
                        'item_name_Text': row.get('name', str(key)),
                        'itemCount_BitmapFontLabel': f'x{count}',
                    }, resources={'icon_Image': icon_of(table, row)})
                    x = area[0] + slot*132
                    y = area[1]
                    layer.alpha_composite(card, (round(x), round(y)))
                    self.ui_hits[f'get_item_{scroll[0]+slot}'] = (
                        x, y, x+128, y+167)
            self.ui_base_layer = layer
            self.ui_hits.update(base_hits)
            self.ui_buttons = base_buttons
            self.ui_rects = base_rects
            self.ui_button_text = base_text
            info.set(f'{title}：{len(items)} 项奖励'
                     + (f' · 滚轮翻页（{scroll[0]//2+1}/{(len(items)+1)//2}）'
                        if len(items) > 2 else ''))
            if getattr(self, 'ui_art_label', None) is not None:
                photo = ImageTk.PhotoImage(layer)
                self.ui_art_label.configure(image=photo)
                self.ui_art_label.image = photo

        def wheel(event):
            if len(items) <= 2:
                return
            step = -1 if event.delta > 0 else 1
            scroll[0] = max(0, min((len(items)-1)//2*2, scroll[0]+2*step))
            paint()
        if hasattr(self, 'ui_art_label'):
            self.ui_art_label.bind('<MouseWheel>', wheel)
        self.ui_actions['confirm_Button'] = self.close_ui
        self.ui_actions['close_Button'] = self.close_ui
        paint()

    def _second_confirm_body(self, body, info):
        text = str(self.ui_parameters.get('text', '确定执行这个操作吗？'))
        if getattr(self, 'ui_art_label', None) is not None:
            layer = self.cocos_ui.render('SecondConfirmUI', (800, 480), {'info_Text': text})
            photo = ImageTk.PhotoImage(layer)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
        info.set(text)
        self.ui_actions['confirm_Button'] = lambda: self.close_ui('yes')
        self.ui_actions['cancel_Button'] = lambda: self.close_ui('no')
        self.ui_actions['close_Button'] = lambda: self.close_ui('no')

    def _tip_body(self, body, info):
        body.pack_forget()
        text = str(self.ui_parameters.get('text', ''))
        if getattr(self, 'ui_art_label', None) is not None:
            layer = self.cocos_ui.render('TipConfirmUI', (800, 480), {'tip_Text': text})
            photo = ImageTk.PhotoImage(layer)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
        info.set(text)
        self.ui_actions['confirm_Button'] = self.close_ui
        self.ui_actions['close_Button'] = self.close_ui

    def confirm_battle(self, request, npcid, fight_type):
        self.open_ui(Request('openui', 'fight-confirm', 1, {
            'parameters': {'uiid': 50, 'text': '要开始这场战斗吗？'}}))
        def yes():
            self.close_ui()
            if not self.start_battle(npcid, kind={3: 'arena', 4: 'budokan', 5: 'infinite_arena'}.get(fight_type)):
                self.drive()
                return
            self.runtime.resume('start')
            self.drive()
        def no():
            self.close_ui()
            self.runtime.resume('no')
            self.drive()
        self.ui_actions['confirm_Button'] = yes
        self.ui_actions['cancel_Button'] = no
        self.ui_actions['close_Button'] = no

    def open_skill_replace(self, uid, key, scroll=None, back=None):
        passive = str(key) in self.data.tables['Talent']
        self.open_ui(Request('openui', 'skill-replace', 1, {
            'parameters': {'uiid': 54, 'uid': uid, 'key': str(key),
                           'passive': passive, 'scroll': scroll, 'back': back}}))

    def _skill_replace_body(self,body,info):
        self._native_skill_replace(body,info)

    def _open_chest_body(self, body, info):
        from original_pages import Page
        body.pack_forget()
        def paint():
            row = self.data.tables['ChestItem']['210001']
            key, count = str(numbers(row['costIds'])[0]), numbers(row['costCounts'])[0]
            page = Page(self, 'OpenChestConfirmUI', timeline_frame=60,
                        text={'title_Text': '需要钥匙开启', 'need_BitmapFontLabel': f'x{count}'},
                        resources={'icon_Sprite': self._item_data(key)[1]}, sizes={'icon_Sprite': (44, 44)},
                        positions={'title_Text': (0, 50)})
            page.actions.update({'confirm_Button': confirm, 'cancel_Button': self.close_ui, 'close_Button': self.close_ui})
            page.publish()
        def confirm():
            try:
                rewards = self.state.open_chest_item()
            except (ValueError, KeyError) as error:
                self._page_tip(str(error), paint)
                return
            info.set('宝箱已开启：' + '、'.join(
                f'{self._item_data(k)[0]}×{n}' for k, n in rewards))
            self.reward_overlay(rewards, self.close_ui, '宝箱获得')
        paint()


    def open_free_pet(self, uid, back=47):
        self.open_ui(Request('openui', 'free-pet', 1, {
            'parameters': {'uiid': 56, 'uid': uid, 'back': back}}))

    def _free_pet_body(self, body, info):
        uid = str(self.ui_parameters.get('uid') or
                  (self.state.pets[0].uid if self.state.pets else ''))
        back_uiid = int(self.ui_parameters.get('back', 47) or 47)
        pet = next((candidate for candidate in self.state.pets
                    if str(candidate.uid) == uid), None)
        if pet is None:
            info.set('这只宠物不在携带栏。')
            return
        name = self.data.tables['Pet'][pet.species]['name']
        text = f'确定放生 {name} Lv.{pet.level} 吗？放生后无法恢复。'
        if getattr(self, 'ui_art_label', None) is not None:
            layer = self.cocos_ui.render('FreePetConfirmUI', (800, 480),
                                         {'info_Text': text})
            photo = ImageTk.PhotoImage(layer)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
        info.set(text)
        def back():
            self.close_ui()
            if back_uiid == 57 and pet in self.state.pets:
                self.open_pet_property(pet.uid)
            else:
                self.pets_ui()
        def confirm():
            if pet is self.state.pets[self.state.active_pet]:
                info.set('出战中宠物不能放生，请先更换出战宠物。')
                return
            index = self.state.pets.index(pet)
            self.state.pets.remove(pet)
            if self.state.active_pet > index:
                self.state.active_pet -= 1
            self.state.active_pet = max(
                0, min(self.state.active_pet, len(self.state.pets)-1))
            back_uiid = 47
            back()
        self.ui_actions['confirm_Button'] = confirm
        self.ui_actions['cancel_Button'] = back
        self.ui_actions['close_Button'] = back

    def open_hatch_check(self, index):
        self.open_ui(Request('openui', 'hatch-check', 1, {
            'parameters': {'uiid': 62, 'index': int(index)}}))

    def _hatch_check_body(self, body, info):
        body.pack_forget()
        self._hatch_check_page(info, int(self.ui_parameters.get('index', 0)))

    def _close_hatch_check(self):
        self.close_ui()

    def open_evolution(self, uid, back=47):
        self.open_ui(Request('openui', 'evolution-condition', 1, {
            'parameters': {'uiid': 61, 'uid': uid, 'back': back}}))

    def _evolution_body(self, body, info):
        self._evolution_page(body, info)


    def open_skill_learn_confirm(self, uid, key, scroll=None, replace=None, back=None):
        pet=next((p for p in self.state.pets if p.uid==str(uid)),None)
        passive=str(key) in self.data.tables['Talent']
        known=([k for k in pet.talents if 400200<=int(k)<400300] if passive else pet.skills) if pet else []
        if pet and str(key) not in [str(k) for k in known] and len(known)>=(2 if passive else 4) and replace is None:
            self.open_skill_replace(uid,key,scroll=scroll,back=back)
            return
        self.open_ui(Request('openui', 'skill-learn-confirm', 1, {
            'parameters': {'uiid': 60, 'uid': uid, 'key': str(key),
                           'scroll': scroll, 'replace': replace, 'back': back}}))

    def _skill_learn_confirm_body(self, body, info):
        body.pack_forget()
        parameters = self.ui_parameters
        uid = str(parameters.get('uid') or
                  (self.state.pets[0].uid if self.state.pets else ''))
        key = str(parameters.get('key') or next(iter(self.data.tables['Skill'])))
        scroll = parameters.get('scroll')
        replace = parameters.get('replace')
        replace = int(replace) if replace is not None else None
        back_uiid = parameters.get('back')
        pet = next((candidate for candidate in self.state.pets
                    if str(candidate.uid) == uid), None)
        if pet is None:
            info.set('这只宠物不在携带栏。')
            return
        table = 'Talent' if key in self.data.tables['Talent'] else 'Skill'
        row = self.data.tables[table].get(key)
        if not row:
            info.set('原版技能表中没有这个技能。')
            return
        if scroll is not None:
            cost = f'卷轴 ×1（{self.data.tables["Item"].get(str(scroll), {}).get("name", scroll)}）'
        else:
            money = self.data.tables['Money'].get(str(row.get('moneyId')), {})
            cost = f'{row.get("moneyCount", 0)} {money.get("name", row.get("moneyId", ""))}'
        name = self.data.tables['Pet'][pet.species]['name']
        text = (f'{name} Lv.{pet.level} 学习 {row["name"]}，消耗 {cost}。'
                + (f' 将替换第 {replace+1} 个技能槽。' if replace is not None else ''))
        if getattr(self, 'ui_art_label', None) is not None:
            from original_pages import Page
            page = Page(self, 'SkillLearnConfirmUI', text={
                'petName_Text': name, 'lv_BitmapFontLabel': str(pet.level),
                'skillName_Text': str(row['name']),
                'skillInfoTitle_Text': '技能介绍：',
                'info_Text': row.get('des',text),
                'cost_BitmapFontLabel': str(row.get('moneyCount', 1) if scroll is None else 1),
                'energy_Text': '能量',
                'energy_BitmapFontLabel': str(row.get('energyCost', 0))},
                resources={'cost_Sprite':self._item_data(scroll or row.get('moneyId','700001'))[1]},
                visible={'energy_Text':table=='Skill','energy_BitmapFontLabel':table=='Skill'})
            page.publish()
        info.set(text)
        def back():
            if back_uiid:
                self.open_ui(Request('openui', 'skill-learn', 1, {
                    'parameters': {'uiid': int(back_uiid)}}))
            else:
                self.close_ui()
        def confirm():
            try:
                with self.state.transaction():
                    self.state.learn_skill(pet.uid,key,scroll=scroll,replace=replace)
                    if not self.save():raise ValueError('保存失败，技能学习未完成。')
            except (ValueError,KeyError) as error:
                self._page_tip(str(error),page.publish)
                return
            back()
            if self.ui_open:self._page_tip('技能学习成功。',self.original_page.publish)
            else:self.scene_ui.show_tip('技能学习成功。')
        self.ui_actions['confirm_Button'] = confirm
        self.ui_actions['close_Button'] = back
        self.ui_window.bind('<Escape>', lambda _event: back())
        self.ui_window.protocol('WM_DELETE_WINDOW',back)

    def _about_body(self, body, info):
        text = self.ui_parameters.get('text') or (
            '口袋妖怪 · 原生 PC 移植开发版 0.2\n\n'
            '使用原版 1.20.4 数据和 Cocos 布局，不是安卓模拟器封装。\n'
            '剧情、战斗、捕捉、养成、道具、任务和界面仍在持续还原；'
            '缺失机制会停在原位置，不伪造结果。')
        if getattr(self, 'ui_art_label', None) is not None:
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            fields = {
                'about_Text_0': lines[0] if lines else '口袋妖怪 · 原生 PC 移植',
                'about_Text_1': '原版数据 1.20.4 · 原生 Windows 开发版',
                'about_Text_2': '不是安卓模拟器封装',
                'about_Text_3': '剧情 / 战斗 / 捕捉 / 养成 / 道具 / 任务持续还原',
                'about_Text_9': '缺失机制会停在原位置，不伪造结果',
                'about_Text_42': '15 个数值函数已与原二进制比较 3,000 组',
                'about_Text_51': '每个可打开界面均使用原版 Cocos 布局',
                'about_Text_52': '',
                'about_Text_56': '',
                'about_Text_57': '',
                'about_Text_58': '',
            }
            layer = self.cocos_ui.render('GameAboutUI', (800, 480), fields)
            photo = ImageTk.PhotoImage(layer)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
        info.set(text)
        def close():
            self.close_ui()
        tk.Button(body, text='关闭', command=close).pack(pady=6)
        self.ui_actions['close_Button'] = close
        self.ui_window.bind('<Escape>', lambda _event: close())

    def open_lucky_pet_info(self, uid, back=None):
        self.open_ui(Request('openui', 'lucky-pet', 1, {
            'parameters': {'uiid': 58, 'uid': uid, 'back': back}}))

    def _lucky_pet_body(self, body, info):
        from original_pages import Page
        body.pack_forget()
        uid = str(self.ui_parameters.get('uid', ''))
        back = self.ui_parameters.get('back')
        pet = next((p for p in self.state.pets+self.state.bank if p.uid == uid), None)
        if pet is None:
            self._page_tip('找不到抽宠记录。', self.close_ui)
            return
        from lottery_animation import LotteryAnimation
        self.lottery_animation = LotteryAnimation(self, [pet], int(self.ui_parameters.get('kind', 1)), back)
        self.lottery_animation.start()


    def open_pet_property(self, uid):
        self.open_ui(Request('openui', 'pet-property', 1, {
            'parameters': {'uiid': 57, 'uid': uid}}))

    def _pet_property_body(self, body, info):
        self._pet_property_page(body, info)

    def _legacy_pet_property_body(self, body, info):
        uid = str(self.ui_parameters.get('uid') or
                  (self.state.pets[0].uid if self.state.pets else ''))
        pet = next((candidate for candidate in self.state.pets
                    if str(candidate.uid) == uid), None)
        if pet is None:
            info.set('这只宠物不在携带栏。')
            return
        tables = self.data.tables
        page = ['skill']
        stats = pet.stats(tables)
        pet_name = tables['Pet'][pet.species]['name']
        if getattr(self, 'ui_art_label', None) is not None:
            layer = self.cocos_ui.render('PetPropertyUI', (800, 480), {
                'name_Text': pet_name, 'lv_BitmapFontLabel': str(pet.level),
                'number_BitmapFontLabel': str(pet.uid),
                'skillInfo_Text': (f'生命 {stats[0]}  能量 {stats[1]}\n'
                                   f'攻击 {stats[2]}  防御 {stats[3]}  速度 {stats[4]}')})
            photo = ImageTk.PhotoImage(layer)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
        frame = tk.Frame(self.ui_window, bg='#202b30', highlightthickness=0)
        rect = self.ui_hits.get('infoSkill_ListView') or self.ui_rects.get('infoSkill_ListView')
        if rect:
            frame.place(x=rect[0], y=rect[1], width=max(160, rect[2]-rect[0]),
                        height=max(80, rect[3]-rect[1]))
            frame.lift()
        else:
            frame.pack(fill='both', expand=True)
        box = tk.Listbox(frame, font=('Microsoft YaHei UI', 9), exportselection=False,
                         bg='#182125', fg='#e8d8b8', selectbackground='#49606a')
        box.pack(fill='both', expand=True)
        rows = []
        def refresh():
            rows.clear()
            box.delete(0, 'end')
            if page[0] == 'skill':
                keys = [str(value) for value in pet.skills]
                table = tables['Skill']
            else:
                keys = [str(value) for value in pet.talents]
                table = tables['Talent']
            for key in keys:
                row = table.get(key)
                if not row:
                    continue
                rows.append(row)
                box.insert('end', str(row.get('name', key)))
            if rows:
                box.selection_set(0)
                show()
            else:
                info.set(f'{pet_name} 没有{"技能" if page[0] == "skill" else "天赋"}。')
        def show(_=None):
            index = box.curselection()
            if not index or index[0] >= len(rows):
                return
            row = rows[index[0]]
            info.set(f'{pet_name} Lv.{pet.level} · {row.get("name", "")}\n'
                     f'{row.get("des", "")}')
        def tag(value):
            page[0] = value
            refresh()
        def evolution():
            self.open_evolution(pet.uid, back=57)
        box.bind('<<ListboxSelect>>', show)
        self.ui_actions['skillTag_Button'] = lambda: tag('skill')
        self.ui_actions['talentTag_Button'] = lambda: tag('talent')
        self.ui_actions['free_Button'] = lambda: self.open_free_pet(pet.uid, back=57)
        self.ui_actions['evolution_Button'] = evolution
        self.ui_actions['close_Button'] = self.close_ui
        self.ui_window.bind('<Escape>', lambda _event: self.close_ui())
        refresh()

    def illustrated_ui(self):
        if self.battle or self.ui_open:
            return
        self.open_ui(Request('openui', 'illustrated', 1, {'parameters': {'uiid': 48}}))


    def pets_ui(self):
        if self.battle:
            self.event_issue = '请在战斗界面使用换宠和道具指令。'
            return
        self.open_ui(Request('openui', 'pet-list', 1, {'parameters': {'uiid': 47}}))

    def _pet_list_body(self, body, info):
        self._pet_list_page(body, info)

    def _legacy_pet_list_body(self, body, info):
            """Original PetListUI: original rows and panels, no host list overlay."""
            state, tables = self.state, self.data.tables
            pets = list(state.pets)
            selected = [0 if pets else -1]
            page = ['base']
            scroll = [0]
            rect = self.ui_rects.get('item_ListView') or self.ui_hits.get('item_ListView')
            if not rect:
                rect = (35, 98, 396, 426)
            body.pack_forget()

            def row_data(pet):
                row = tables['Pet'][pet.species]
                stats = pet.stats(tables)
                return row, stats

            def paint():
                now = page[0]
                visible = {
                    'baseInfo_Panel': now == 'base',
                    'skillInfo_Panel': now in ('skill', 'talent'),
                    'train_ProjectNode': now == 'train',
                }
                text = {'progress_BitmapFontLabel': f'{len(pets)}/200'}
                layer = self.cocos_ui.render('PetListUI', (800, 480), text, visible=visible)
                base_hits = dict(self.cocos_ui.hits)
                base_rects = dict(self.cocos_ui.rects)
                base_buttons = dict(self.cocos_ui.buttons)
                base_text = dict(self.cocos_ui.button_text)
                draw = ImageDraw.Draw(layer)

                # Original PetListItemUI rows are 320x110 and the original list
                # viewport is 361x328, so three rows fit without a host Listbox.
                for index, pet in enumerate(pets[scroll[0]:scroll[0]+3]):
                    row, stats = row_data(pet)
                    row_layer = self.cocos_ui.render(
                        'PetListItemUI', (320, 110),
                        {'name_Text': row['name'],
                         'lv_BitmapFontLabel': str(pet.level),
                         'hpHave_BitmapFontLabel': str(pet.hp),
                         'hpMax_BitmapFontLabel': str(stats[0]),
                         'enHave_BitmapFontLabel': str(pet.energy),
                         'enMax_BitmapFontLabel': str(stats[1]),
                         'friendly_BitmapFontLabel': str(pet.friendly)},
                        visible={'add_Panel': False})
                    x = round(rect[0] + 20)
                    y = round(rect[1] + index * 110)
                    layer.alpha_composite(row_layer, (x, y))
                    self.ui_hits[f'pet_row_{index}'] = (x, y, x+320, y+110)
                    if scroll[0] + index == selected[0]:
                        draw.rectangle((x+1, y+1, x+318, y+108),
                                       outline='#ffe36e', width=3)

                # Put the selected pet's original full-body image on petPos_Node.
                if now == 'base' and pets:
                    pet = pets[selected[0]]
                    art = self.data.pet_image(pet.species)
                    if art is not None:
                        art = art.copy()
                        art.thumbnail((190, 225), Image.Resampling.LANCZOS)
                        layer.alpha_composite(art, (487-art.width//2, 258-art.height//2))

                def put(x, y, value, size=12, fill=(76, 48, 30)):
                    font_path = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts/msyh.ttc'
                    try:
                        font = ImageFont.truetype(str(font_path), size)
                    except OSError:
                        font = ImageFont.load_default()
                    for dx, dy in ((1, 1), (0, 0)):
                        draw.text((x+dx, y+dy), value, font=font,
                                  fill=(255, 250, 235) if (dx, dy) == (1, 1) else fill)

                if now == 'base' and pets:
                    pet = pets[selected[0]]
                    row, stats = row_data(pet)
                    active = ' · 出战' if selected[0] == state.active_pet else ''
                    put(420, 116, f'{row["name"]} Lv.{pet.level}{active}', 13)
                    put(422, 316, f'生命 {pet.hp}/{stats[0]}\n能量 {pet.energy}/{stats[1]}',
                        11, (255, 244, 209))
                    put(565, 316, f'力量 {stats[2]}\n防御 {stats[3]}\n速度 {stats[4]}',
                        11, (255, 244, 209))
                    put(565, 356, f'品质 {pet.quality}  突破 {pet.breakthrough}  '
                                   f'亲密 {pet.friendly}', 9, (255, 244, 209))
                elif now in ('skill', 'talent') and pets:
                    pet = pets[selected[0]]
                    if now == 'skill':
                        values = [tables['Skill'].get(str(s), {}).get('name', str(s))
                                  for s in pet.skills]
                        title = '技能'
                    else:
                        values = [tables['Talent'].get(str(t), {}).get('name', str(t))
                                  for t in pet.talents]
                        title = '天赋'
                    put(437, 154, title, 14, (255, 244, 209))
                    for index, value in enumerate(values[:5]):
                        put(444, 176 + index*18, f'· {value}', 12, (255, 244, 209))
                    if not values:
                        put(444, 176, '（无）', 12, (255, 244, 209))
                elif now == 'train' and pets:
                    pet = pets[selected[0]]
                    row, stats = row_data(pet)
                    put(424, 319, f'训练值会加入属性：生命 {stats[0]} / 能量 {stats[1]} / '
                                    f'力量 {stats[2]} / 防御 {stats[3]} / 速度 {stats[4]}', 11)

                self.ui_base_layer = layer
                self.ui_hits.update(base_hits)
                self.ui_rects = base_rects
                self.ui_buttons = base_buttons
                self.ui_button_text = base_text
                self.ui_actions['pet_row_0'] = lambda: choose(scroll[0])
                self.ui_actions['pet_row_1'] = lambda: choose(scroll[0]+1)
                self.ui_actions['pet_row_2'] = lambda: choose(scroll[0]+2)
                if hasattr(self, 'ui_art_label') and self.ui_art_label.winfo_exists():
                    photo = ImageTk.PhotoImage(layer)
                    self.ui_art_label.configure(image=photo)
                    self.ui_art_label.image = photo

            def choose(index):
                if not 0 <= index < len(pets):
                    return
                selected[0] = index
                page[0] = 'base'
                row, stats = row_data(pets[index])
                info.set(f'{row["name"]} · Lv.{pets[index].level} · '
                         f'生命 {pets[index].hp}/{stats[0]}')
                paint()

            def rebuild():
                nonlocal pets
                pets = list(state.pets)
                if not pets:
                    selected[0] = -1
                else:
                    selected[0] = min(max(0, selected[0]), len(pets)-1)
                paint()

            def join_battle():
                if not pets:
                    return
                state.active_pet = selected[0]
                rebuild()

            def evolve():
                if pets:
                    self.open_evolution(pets[selected[0]].uid)

            def free():
                if not pets:
                    return
                if selected[0] == state.active_pet:
                    info.set('出战中宠物不能放生，请先更换出战宠物。')
                    return
                self.open_free_pet(pets[selected[0]].uid)

            def use_item():
                if not pets:
                    return
                self.bag_target_uid = pets[selected[0]].uid
                self.close_ui()
                self.bag_ui()

            def tag(value):
                if not pets:
                    return
                page[0] = value
                paint()

            def wheel(event):
                step = -1 if event.delta > 0 else 1
                top = max(0, len(pets)-3)
                scroll[0] = min(top, max(0, scroll[0]+step))
                paint()

            self.ui_actions.update({
                'joinBattle_Button': join_battle,
                'evolution_Button': evolve,
                'useItem_Button': use_item,
                'free_Button': free,
                'skillTag_Button': lambda: tag('skill'),
                'talentTag_Button': lambda: tag('talent'),
                'skill_Button': lambda: tag('skill'),
                'trainValue_Button': lambda: tag('train'),
                'close_Button': self.close_ui,
            })
            if hasattr(self, 'ui_art_label'):
                self.ui_art_label.bind('<MouseWheel>', wheel)
            rebuild()

    def store_ui(self):
        if self.battle:
            self.event_issue = '请先结束战斗。'
            return
        if self.ui_open:
            return
        self.open_ui(Request('openui', 'store', 1,
                            {'parameters': {'uiid': 63}}))

    def recharge_ui(self):
        if self.battle:
            self.event_issue = '请先结束战斗。'
            return
        if self.ui_open:
            return
        self.open_ui(Request('openui', 'recharge', 1,
                            {'parameters': {'uiid': 63}}))

    def bag_ui(self):
        if self.battle:
            self.event_issue = '请在战斗界面使用道具指令。'
            return
        self.open_ui(Request('openui', 'bag', 1, {'parameters': {'uiid': 46}}))


    def tasks_ui(self):
        TaskProgress(self.state).update()
        self.open_ui(Request('openui', 'task-menu', 1, {'parameters': {'uiid': 44}}))

    def about(self):
        text = ('原生开发版 0.2，尚未完成所有内容。\n\n'
            '已接入：真实冠军赛序章与主线 1–6、461 条触发规则、任务与事件条件、分支解释器、'
            '原版战斗核心（伤害/属性克制/暴击/状态/捕捉/经验/掉落）、原版 Cocos 战斗界面、'
            '初始宠物选择、任务目标解析与跨图自动指引、原版背包/宠物列表/图鉴/获得物品/确认框、'
            '商店/治疗/地图等界面入口、独立持久化。\n\n'
            '15 个独立数值函数已与原二进制进行 3,000 组比较。\n'
            '仍在移植：全部 57 种状态、天赋/携带物完整结算、宠物融合后续、完整任务与剧情分支、'
            '战斗内存档、全部支线与结局。遇到缺失机制会停在原位置，不伪造结果。')
        if self.battle or self.ui_open:
            self.event_issue = text
            return
        self.open_ui(Request('openui', 'about-tip', 1, {
            'parameters': {'uiid': 59, 'text': text}}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--screenshot', type=Path)
    args = parser.parse_args()
    root = tk.Tk()
    app = NativeGame(root, OriginalData(data_root()), show_opening=True)
    if args.screenshot:
        app.make_frame().convert('RGB').save(args.screenshot)
        root.after(200, root.destroy)
    if args.smoke_test:
        root.after(1200, root.destroy)
    root.mainloop()


if __name__ == '__main__':
    main()
