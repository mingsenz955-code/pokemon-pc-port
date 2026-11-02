"""Native host for the original-state runtime. Incomplete mechanics stop explicitly."""
from __future__ import annotations

import argparse
import json
import math
import os
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk

from original_data import OriginalData
from pc_preview import Preview, data_root
from game_state import GameState
from event_runtime import EventRuntime, PendingMechanic, Request
from csb_render import CocosUI
from battle import make_npc_battle, make_wild_battle
from arena import ArenaProgress, make_arena_battle
from infinite_arena import InfiniteArenaProgress, make_infinite_arena_battle
from budokan import BudokanProgress, make_budokan_battle
from battle_ui import BattleUI
from activity_ui import ActivityUI
from daily_tasks import DailyTasks
from achievements import Achievements
from task_progress import TaskProgress
from mounts import Mounts
from guide import Guide, GuideTarget
from story_motion import StoryMotion, FACES
from scene_ui import SceneUI
from npc_motion import NpcMotion


class NativeGame(ActivityUI, Preview):
    WIDTH, HEIGHT = 960, 576  # Uniform 1.2x of the original 800x480 design.
    DYNAMIC_SCENERY = True
    def __init__(self, root, data):
        self.state = GameState(data.tables)
        self.cocos_ui = CocosUI(data)
        self.runtime = EventRuntime(data, self.state)
        self.booting = True
        self.runtime_error = ''
        self.display_request = None
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
        self.canvas.bind('<Button-1>', self.on_click)
        self.canvas.bind('<ButtonRelease-1>', lambda e: self.task_page_event('release', e))
        self.canvas.bind('<B1-Motion>', lambda e: self.task_page_event('motion', e))
        self.canvas.bind('<MouseWheel>', self.on_canvas_wheel)
        root.title('口袋妖怪 · 原生 PC 移植开发版 0.2.53（全系统还原进行中）')
        top = root.winfo_children()[0]
        top.destroy()
        for child in root.winfo_children():
            if isinstance(child, tk.Label):
                child.pack_forget()
        default_save = Path(os.environ.get('LOCALAPPDATA', str(Path.home())))/'PocketNativePC'
        self.save_path = Path(os.environ.get('POCKET_NATIVE_SAVE_DIR', str(default_save)))/'slot1.json'
        if self.save_path.exists() and self.restore():
            return
        self.load_map(7401, 17*64+32, (30-14)*64)
        self.reset_encounter()
        self.runtime.notify('tomap', map=7401)
        self.drive()

    def load_map(self, mid, x=None, y=None):
        super().load_map(mid, x, y)
        self.chest_fx = None
        self.obstacle_fx = None
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
        if changed:
            self.background = self.map.render(self.SCALE, include_objects=False)

    def break_obstacle(self, obs_type, tx, ty):
        """Break/cut an obsType sprite only when the current ride has the ability."""
        mounts = Mounts(self.state)
        if not mounts.obstacle_ability(obs_type):
            return False
        if self.map.remove_obstacle(tx, ty) is None:
            return False
        self.state.removed_obstacles.append([int(self.map_id), int(tx), int(ty), int(obs_type)])
        self.background = self.map.render(self.SCALE, include_objects=False)
        self.obstacle_fx = {'x': int(tx)*self.map.tw+self.map.tw/2,
                            'y': int(ty)*self.map.th+self.map.th/2,
                            'type': int(obs_type), 'age': 0}
        TaskProgress(self.state).update('obstacle', int(obs_type))
        if self.pending_wait and self.pending_wait.kind == 'wait':
            params = self.pending_wait.data.get('parameters', {})
            if int(params.get('type', 0) or 0) == 3:
                self.pending_wait = None
                self.wait_until = 0
                self.event_issue = ''
                self.runtime.resume()
                # Do not run the next event step inside move_to: a following
                # toplace/goto may replace self.map while the caller is still
                # finishing this movement.
                self.root.after(0, self.drive)
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
                pass
            else:
                return
        mounts.enter(self.map.terrain_at(x, y), int(self.map.info['mapType']))
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
        rows = [(0, '步行 / 下坐骑')]
        for key, row in self.data.tables['Ride'].items():
            owned = int(key) in [int(k) for k in self.state.rides]
            rows.append((int(key), row['name'] + (' · 已获得' if owned else ' · 未获得')))
        def select(key):
            try:
                Mounts(self.state).select(key, self.map.terrain_at(self.x, self.y),
                                          int(self.map.info['mapType']))
            except ValueError as error:
                messagebox.showinfo('坐骑', str(error), parent=self.root)
        self.choose('坐骑', rows, select)

    def player_image(self, face):
        row = Mounts(self.state).active()
        if row:
            animation = 'standleft' if face == 'standright' else face
            image = self.data.armature(row['filePath'], animation)
            if image is not None:
                return image.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if face == 'standright' else image
        return super().player_image(face)

    def check_encounter(self):
        if self.battle or self.runtime.running or self.ui_open or self.display_request or self.pending_wait:
            return False
        if self.encounter_threshold <= 0 or self.encounter_distance < self.encounter_threshold*64:
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
            self.start_battle(enemy_id, 'wild')
        except PendingMechanic as error:
            self.runtime_error = str(error)
            return False
        return True

    def play_event(self, filename):
        if self.booting:
            return
        if self.runtime.running:
            return
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
            key = f'{self.map_id}:2:{oid}'
            visible = self.state.visible.get(key, int(obj['props'].get('state', '1')) != 0)
            if not visible:
                continue
            sid = self.map.tile_properties(int(obj['gid'])).get('spriteId')
            if not sid:
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
        obj = next((o for o in self.map.objects if o.get('gid') and str(o.get('name')) == str(oid)), {})
        fallback = FACES.get(int(obj.get('props', {}).get('face', 2)), 'standdown')
        ambient = getattr(self, 'npc_motion', None)
        if ambient and any(str(a['id']) == str(identifier) for a in ambient.motion.actions):
            return ambient.motion.animation(kind, identifier, fallback)
        return self.story_motion.animation(kind, identifier, fallback)

    def scene_sprite(self, sid, animation):
        frame = int(getattr(self, 'scene_animation_time', 0)*60) if animation.startswith(('walk', 'stand')) else 0
        return self.data.village_sprite(sid, animation, frame)

    def render_actor_overlay(self, frame, oid, sid, sx, sy, sprite, anchor):
        if self.booting or not str(oid).isdigit() or not str(sid).isdigit() or not 20000 <= int(sid) < 30000:
            return
        from task_icons import TaskIcons
        resolver = getattr(self, 'task_icons', None)
        if resolver is None or resolver.state is not self.state:
            resolver = self.task_icons = TaskIcons(self.state)
        icon_id = resolver.for_npc(oid)
        if not icon_id:
            return
        icon = self.data.image(f'TaskIcon/taskIcon{icon_id}.png')
        scale = self.SCALE*.5
        icon = icon.resize((max(1, round(icon.width*scale)), max(1, round(icon.height*scale))), Image.Resampling.LANCZOS)
        bob = resolver.bob(getattr(self, 'scene_animation_time', 0))*self.SCALE
        top = sy-anchor[1]*self.SCALE-icon.height+bob
        frame.alpha_composite(icon, (round(sx-icon.width/2), round(top)))

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
        return self.scene_sprite(self.player_sprite, animation)

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
        7: ('ChoiceFirstPetUI', '初始宠物'), 8: ('IllustratedPetInfoUI', '宠物图鉴'),
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
        63: ('RechargeFreeUI', '充值奖励'),
        64: ('PublicNoticeUI', '公告'),
        65: ('SystemUI', '系统设置'),
        66: ('BluetoothListUI', '蓝牙'),
        67: ('AsideUI', '侧边栏'),
    }

    def open_ui(self, request):
        parameters = request.data.get('parameters', {})
        self.ui_parameters = parameters
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
        if uiid == 7:
            self.starter_window(int(parameters.get('par1', 1)))
            return
        layout, name = self.UI_LAYOUTS.get(uiid, ('MainUI', f'原版界面 {uiid}'))
        if self.ui_window and self.ui_window.winfo_exists():
            self.ui_window.destroy()
        win = tk.Toplevel(self.root)
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
            label = tk.Label(win, image=photo, bg='#101418')
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
            info.set(f'治疗全部携带宠物：{cost} {self.data.tables["Money"][currency]["name"]}' if currency else '医疗卡治疗免费。')
            def cure():
                try:
                    self.heal_party()
                    info.set('全部携带宠物已恢复。')
                except ValueError as error:
                    info.set(str(error))
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
            info.set('这里是原版充值奖励入口。当前单机移植不接入真实支付，'
                     '不会伪造充值到账或扣费；可关闭本页继续游戏。')
            self.ui_actions['confirm_Button'] = lambda: info.set(
                '单机版没有计费点，不能伪造免费领取；请关闭本页。')
        elif uiid == 64:
            info.set('原版公告页。单机版没有联网公告服务，'
                     '这里不伪造运营公告；关闭后可继续游戏。')
            self.ui_actions['confirm_Button'] = self.close_ui
            self.ui_actions['close_Button'] = self.close_ui
            body.pack_forget()
        elif uiid == 65:
            info.set('原版系统设置页。音乐/音效开关尚未接入宿主音频，'
                     '不会伪装成已生效。')
            self.ui_actions['close_Button'] = self.close_ui
            self.ui_actions['about_Button'] = self.about
            for name in ('moreGame_Button', 'control_click_Button',
                         'control_direct_Button', 'music_open_Button',
                         'music_close_Button', 'effect_open_Button',
                         'effect_close_Button'):
                self.ui_actions[name] = lambda: info.set(
                    '该设置项尚未接入，当前不会修改游戏状态。')
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
        elif uiid == 6:
            self._skill_body(body, info)
        elif uiid == 5:
            self._hatch_body(body, info)
        elif uiid in (16, 17):
            self._pet_shop_body(body, info, parameters.get('par1') or 601)
        elif uiid in (1, 2, 3, 22, 28):
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
            self._treasure_body(body, info, parameters.get('par1'))
        elif uiid == 37:
            self._treasure_buy_body(body, info, parameters.get('par1'))
        elif uiid == 38:
            self._treasure_tip_body(body, info)
        elif uiid in (27, 36):
            info.set('原版礼包购买入口；支付与奖励表尚未接入，不能伪造发货。')
            self.ui_actions['buy_Button'] = lambda: info.set('礼包购买与奖励表尚未接入，未扣除货币。')
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
                candidates.append((0 if is_button else 1, area, name))
        if not candidates:
            return None
        name = min(candidates)[2]
        return name, self.ui_button_text.get(name, '')

    def ui_action_for(self, name):
        base = name.rsplit('/', 1)[-1]
        return self.ui_actions.get(name) or self.ui_actions.get(base)

    def on_ui_click(self, event):
        if not self.ui_window or not self.ui_window.winfo_exists():
            return
        hit = self.ui_hit_at(event.x, event.y)
        if not hit:
            return
        name, label = hit
        base = name.rsplit('/', 1)[-1]
        callback = self.ui_action_for(name)
        if callback:
            try:
                callback()
            except (ValueError, KeyError, PendingMechanic) as error:
                if self.ui_info:
                    self.ui_info.set(str(error))
            return
        if base in {'close_Button', 'closeButton', 'leave_Button', 'cancel_Button',
                    'cancelButton', 'giveUp_Button', 'takeBack_Button'}:
            self.close_ui()
            return
        if self.ui_info:
            shown = label or base
            self.ui_info.set(f'原版按钮「{shown}」尚未接入对应玩法。')

    def on_ui_press(self, event):
        hit = self.ui_hit_at(event.x, event.y)
        self.ui_pressed = hit[0] if hit else None
        self._paint_hover()

    def on_ui_release(self, event):
        hit = self.ui_hit_at(event.x, event.y)
        pressed = self.ui_pressed
        self.ui_pressed = None
        self._paint_hover()
        if hit and pressed == hit[0]:
            self.on_ui_click(event)

    def _paint_hover(self):
        if not self.ui_base_layer or not hasattr(self, 'ui_art_label'):
            return
        if not self.ui_art_label.winfo_exists():
            return
        layer = None
        active = self.ui_pressed or (self.ui_hover[0] if self.ui_hover else None)
        if active and self.ui_render_args:
            # Prefer the original pressed texture for the button being pressed.
            pressed = {active: True}
            try:
                args = self.ui_render_args
                layer = self.cocos_ui.render(args['name'], args['size'], args.get('text'),
                                             args.get('visible'), args.get('resources'),
                                             pressed=pressed)
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
        photo = ImageTk.PhotoImage(layer)
        self.ui_art_label.configure(image=photo)
        self.ui_art_label.image = photo

    def on_ui_motion(self, event):
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

    def _shop_body(self, body, info, uiid):
        table = {1: 'Shop', 2: 'EvolutionShop', 3: 'SkillShop',
                 22: 'IArenaShop', 28: 'MedalShop'}[uiid]
        layout = {1: 'ShopUI', 2: 'EvolutionShopUI', 3: 'SkillShopUI',
                  22: 'InfiniteArenaShopUI', 28: 'MedalShopUI'}[uiid]
        self.shop_uiid = uiid
        clerk = {1: '1', 2: '3', 3: '4'}.get(uiid)
        if clerk:
            talks = dict(self.state.activities.get('shop_talks', {}))
            talks[clerk] = int(talks.get(clerk, 0))+1
            self.state.activities['shop_talks'] = talks
        goods = []
        for goods_key, row in sorted(self.data.tables[table].items(), key=lambda pair: int(pair[0])):
            if str(row.get('repeat', '1')) == '0' and self.state.shop_purchases.get(f'{table}:{goods_key}'):
                continue
            goods.append((str(goods_key), row))
        current = [0]
        scroll = [0]
        info.set(f'商店共 {len(goods)} 件商品 · 持有金币 {self.state.count("700001")}'
                 + (' · 滚轮翻页' if len(goods) > 8 else ''))
        body.pack_forget()

        def choose(index):
            if not 0 <= index < len(goods):
                return
            current[0] = index
            key, row = goods[index]
            self.open_goods_detail(uiid, table, key, row)

        def paint():
            money_text = {
                'Layer/root_Panel/badge_ProjectNode/Layer/root_Panel/goldCount_BitmapFontLabel':
                    str(self.state.count('700002')),
                'Layer/root_Panel/gold_ProjectNode/Layer/root_Panel/goldCount_BitmapFontLabel':
                    str(self.state.count('700001')),
            }
            layer = self.cocos_ui.render(layout, (800, 480),
                                         {'info_Text': info.get(), **money_text},
                                         resources={
                                             'Layer/root_Panel/badge_ProjectNode/Layer/root_Panel/icon_Sprite':
                                                 'UI/money_little_icon_badge.png',
                                             'Layer/root_Panel/gold_ProjectNode/Layer/root_Panel/icon_Sprite':
                                                 'UI/money_little_icon_gold.png',
                                         })
            base_hits = dict(self.cocos_ui.hits)
            base_buttons = dict(self.cocos_ui.buttons)
            base_rects = dict(self.cocos_ui.rects)
            base_text = dict(self.cocos_ui.button_text)
            for old in [key for key in self.ui_actions if key.startswith('shop_goods_')]:
                self.ui_actions.pop(old, None)
            for old in [key for key in self.ui_hits if key.startswith('shop_goods_')]:
                self.ui_hits.pop(old, None)
            rect = base_rects.get('goods_ListView') or base_hits.get('goods_ListView')
            if rect:
                cell_w = (rect[2]-rect[0])/4
                cell_h = (rect[3]-rect[1])/2
                page = goods[scroll[0]:scroll[0]+8]
                for slot, (key, row) in enumerate(page):
                    index = scroll[0]+slot
                    column, line = slot % 4, slot // 4
                    card = self.render_component('GoodsItemNode', (126, 126),
                        {'name_Text': row['name'],
                         'count_BitmapFontLabel': f'x{row.get("count", 1)}'},
                        resources={'icon_Image': f'ItemIcon/{row.get("texture", "")}'},
                        positions={'root_Panel': [63, 63]})
                    x = rect[0]+column*cell_w+(cell_w-126)/2
                    y = rect[1]+line*cell_h+(cell_h-126)/2
                    layer.alpha_composite(card, (round(x), round(y)))
                    self.ui_hits[f'shop_goods_{index}'] = (
                        x, y, x+126, y+126)
                    self.ui_actions[f'shop_goods_{index}'] = (
                        lambda value=index: choose(value))
            self.ui_base_layer = layer
            self.ui_hits.update(base_hits)
            self.ui_buttons = base_buttons
            self.ui_rects = base_rects
            self.ui_button_text = base_text
            self.ui_actions['shop_buy'] = buy
            self.ui_actions['shop_detail'] = detail
            self.ui_actions['close_Button'] = self.close_ui
            if hasattr(self, 'ui_art_label') and self.ui_art_label.winfo_exists():
                photo = ImageTk.PhotoImage(layer)
                self.ui_art_label.configure(image=photo)
                self.ui_art_label.image = photo

        def wheel(event):
            page(-1 if event.delta > 0 else 1)

        def page(step):
            if not goods:
                return
            scroll[0] = max(0, min(len(goods)-1, scroll[0]+8*step))
            info.set(f'商店共 {len(goods)} 件商品 · 第 {scroll[0]//8+1}/{(len(goods)+7)//8} 页 · '
                     f'持有金币 {self.state.count("700001")}')
            paint()
        self.shop_scroll = page
        if hasattr(self, 'ui_art_label'):
            self.ui_art_label.bind('<MouseWheel>', wheel)

        def detail():
            if not goods:
                return
            key, row = goods[current[0]]
            self.open_goods_detail(uiid, table, key, row)

        def buy():
            if not goods:
                return
            key, row = goods[current[0]]
            try:
                self.state.buy(table, key)
                info.set(f'购买 {row["name"]} 成功 · 剩余 {self.state.count(row["moneyType"])}')
            except (ValueError, KeyError, NotImplementedError) as error:
                info.set(str(error))
            paint()

        paint()

    def open_goods_detail(self, shop_uiid, table, key, row):
        self.open_ui(Request('openui', 'shop-goods', 1, {
            'parameters': {'uiid': 52, 'table': table, 'key': key,
                           'shop_uiid': shop_uiid}}))

    def _back_to_shop(self, shop_uiid):
        self.close_ui()
        self.open_ui(Request('openui', 'shop-return', 1, {
            'parameters': {'uiid': shop_uiid}}))

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

    def _shop_goods_body(self, body, info):
        parameters = self.ui_parameters
        table = str(parameters.get('table', 'Shop'))
        key = parameters.get('key')
        if key is None:
            key = sorted(self.data.tables[table].items(), key=lambda pair: int(pair[0]))[0][0]
        key = str(key)
        shop_uiid = int(parameters.get('shop_uiid', 1))
        row = self.data.tables[table][key]
        currency = self.data.tables['Money'].get(str(row['moneyType']), {}).get('name', row['moneyType'])
        detail_text = f'{row["name"]} · {row["price"]} {currency}\n{row.get("des", "")}'
        info.set(detail_text)
        if getattr(self, 'ui_art_label', None) is not None:
            base = self.cocos_ui.render('ShopUI', (800, 480), {
                'info_Text': detail_text,
                'Layer/root_Panel/badge_ProjectNode/Layer/root_Panel/goldCount_BitmapFontLabel':
                    str(self.state.count('700002')),
                'Layer/root_Panel/gold_ProjectNode/Layer/root_Panel/goldCount_BitmapFontLabel':
                    str(self.state.count('700001')),
            }, visible={'info_Text': False}, resources={
                'Layer/root_Panel/badge_ProjectNode/Layer/root_Panel/icon_Sprite':
                    'UI/money_little_icon_badge.png',
                'Layer/root_Panel/gold_ProjectNode/Layer/root_Panel/icon_Sprite':
                    'UI/money_little_icon_gold.png',
            })
            base_buttons = dict(self.cocos_ui.buttons)
            card = self.cocos_ui.render('ShopGoodsUI', (153, 233), {
                'name_Text': row['name'],
                'cost_BitmapFontLabel': str(row['price']),
                'count_BitmapFontLabel': f'x{row.get("count", 1)}',
            }, resources={
                'moneyIcon_Image': 'UI/' + (
                    self.data.tables['Money'].get(str(row['moneyType']), {})
                    .get('littleIconTexture', 'money_little_icon_gold.png')),
                'icon_Image': f'ItemIcon/{row.get("texture", "")}',
            })
            card_buttons = dict(self.cocos_ui.buttons)
            card = card.resize((184, 280), Image.Resampling.LANCZOS)
            base.alpha_composite(card, (320, 90))
            self.ui_base_layer = base
            photo = ImageTk.PhotoImage(base)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
            self.ui_buttons = {key: rect for key, rect in base_buttons.items()
                               if key in ('close_Button', 'Layer/close_Button')}
            self.ui_hits = dict(self.ui_buttons)
            buy_rect = card_buttons.get('buy_Button') or card_buttons.get(
                'Layer/root_Panel/buy_Button')
            if buy_rect:
                shifted = [320+buy_rect[0]*1.2, 90+buy_rect[1]*1.2,
                           320+buy_rect[2]*1.2, 90+buy_rect[3]*1.2]
                self.ui_buttons['buy_Button'] = shifted
                self.ui_hits['buy_Button'] = shifted
        info.set(f'{row["name"]} · {row["price"]} {currency}\n{row.get("des", "")}')
        def buy():
            self.open_ui(Request('openui', 'goods-confirm', 1, {
                'parameters': {'uiid': 53, 'table': table, 'key': key,
                               'shop_uiid': shop_uiid}}))
        self.ui_actions['buy_Button'] = buy
        self.ui_actions['close_Button'] = self.close_ui
        body.pack_forget()

    def _goods_confirm_body(self, body, info):
        parameters = self.ui_parameters
        table = str(parameters.get('table', 'Shop'))
        key = parameters.get('key')
        if key is None:
            key = sorted(self.data.tables[table].items(), key=lambda pair: int(pair[0]))[0][0]
        key = str(key)
        shop_uiid = int(parameters.get('shop_uiid', 1))
        row = self.data.tables[table][key]
        money = self.data.tables['Money'].get(str(row['moneyType']), {})
        currency = money.get('name', row['moneyType'])
        quantity = [1]

        def paint():
            back = self.cocos_ui.render('ShopUI', (800, 480), {
                'Layer/root_Panel/badge_ProjectNode/Layer/root_Panel/goldCount_BitmapFontLabel':
                    str(self.state.count('700002')),
                'Layer/root_Panel/gold_ProjectNode/Layer/root_Panel/goldCount_BitmapFontLabel':
                    str(self.state.count('700001')),
            }, visible={'info_Text': False}, resources={
                'Layer/root_Panel/badge_ProjectNode/Layer/root_Panel/icon_Sprite':
                    'UI/money_little_icon_badge.png',
                'Layer/root_Panel/gold_ProjectNode/Layer/root_Panel/icon_Sprite':
                    'UI/money_little_icon_gold.png',
            })
            layer = self.cocos_ui.render('BuyConfirmUI', (800, 480), {
                'name_Text': row['name'],
                'count_BitmapFontLabel': str(quantity[0]),
                'getItemCount_BitmapFontLabel': f'x{quantity[0]}',
                'costCount_BitmapFontLabel': str(int(row['price']) * quantity[0]),
            }, resources={
                'icon_Sprite': f'ItemIcon/{row.get("texture", "")}',
                'moneyIcon_Sprite': 'UI/' + money.get('littleIconTexture',
                                                      'money_little_icon_gold.png'),
            })
            back.alpha_composite(layer)
            layer = back
            self.ui_base_layer = layer
            self.ui_hits = dict(self.cocos_ui.hits)
            self.ui_rects = dict(self.cocos_ui.rects)
            self.ui_buttons = dict(self.cocos_ui.buttons)
            self.ui_button_text = dict(self.cocos_ui.button_text)
            if getattr(self, 'ui_art_label', None) is not None:
                photo = ImageTk.PhotoImage(layer)
                self.ui_art_label.configure(image=photo)
                self.ui_art_label.image = photo

        def change(step):
            quantity[0] = max(1, min(99, quantity[0] + step))
            info.set(f'{row["name"]} × {quantity[0]} · 共需 '
                     f'{int(row["price"]) * quantity[0]} {currency}')
            paint()

        def confirm():
            try:
                self.state.buy(table, key, quantity[0])
            except (ValueError, KeyError, NotImplementedError) as error:
                messagebox.showwarning('购买失败', str(error), parent=self.ui_window)
                return
            self._back_to_shop(shop_uiid)

        def cancel():
            self._back_to_shop(shop_uiid)

        self.ui_actions['left_Button'] = lambda: change(-1)
        self.ui_actions['right_Button'] = lambda: change(1)
        self.ui_actions['confirm_Button'] = confirm
        self.ui_actions['cancel_Button'] = cancel
        self.ui_actions['buy_Button'] = confirm
        self.ui_actions['close_Button'] = cancel
        info.set(f'{row["name"]} × 1 · 共需 {row["price"]} {currency}')
        paint()
        body.pack_forget()

    def heal_party(self):
        self.state.cure_party()

    def accept_task_ui(self, request):
        """AcceptBTaskUI: original layout/buttons and a real yes/no choice."""
        parameters = request.data.get('parameters', {})
        key = str(parameters.get('btask', ''))
        row = self.data.tables['BranchTask'].get(key)
        if not row:
            self.display_request = None
            self.runtime.resume(False)
            self.drive()
            return
        self.display_request = request
        win = tk.Toplevel(self.root)
        self.accept_task_window = win
        win.title('接受支线任务 · 原版界面')
        win.transient(self.root)
        win.resizable(False, False)
        layer = None
        buttons = {}
        try:
            layer = self.cocos_ui.render(
                'AcceptBTaskUI', (800, 480),
                {'name_Text': row['name'], 'info_Text': row['des']})
            buttons = dict(self.cocos_ui.buttons)
        except (FileNotFoundError, ValueError, KeyError, OSError):
            layer = None
        self.accept_task_buttons = dict(buttons)
        if layer is not None:
            photo = ImageTk.PhotoImage(layer)
            art = tk.Label(win, image=photo, bg='#101418')
            art.image = photo
            art.pack()
            art.bind('<Button-1>', lambda event: click_art(event.x, event.y))
        else:
            tk.Label(win, text='AcceptBTaskUI 原版布局读取失败。', fg='#ffb0a0',
                     bg='#202b30').pack(padx=20, pady=20)

        rewards = []
        reward_ids = [int(v) for v in str(row.get('rewardIds', '')).split(',') if v.strip()]
        reward_counts = [int(v) for v in str(row.get('rewardCounts', '')).split(',') if v.strip()]
        for item_id, count in zip(reward_ids, reward_counts):
            item = (self.data.tables.get('Item', {}).get(str(item_id))
                    or self.data.tables.get('Pet', {}).get(str(item_id))
                    or self.data.tables.get('Money', {}).get(str(item_id)))
            rewards.append(f'{item.get("name", item_id) if item else item_id}×{count}')
        body = tk.Frame(win, bg='#202b30')
        body.pack(fill='x', padx=12, pady=8)
        tk.Label(body, text=row['name'], bg='#202b30', fg='#f2e7cf',
                 font=('Microsoft YaHei UI', 13, 'bold'), anchor='w').pack(fill='x')
        tk.Label(body, text=row['des'].replace('#1', '').replace('#4', '').replace('#0', ''),
                 bg='#202b30', fg='#e8d8b8', justify='left', wraplength=760,
                 font=('Microsoft YaHei UI', 10), anchor='w').pack(fill='x', pady=4)
        if rewards:
            tk.Label(body, text='奖励：'+'、'.join(rewards), bg='#202b30', fg='#f5d28a',
                     font=('Microsoft YaHei UI', 10), anchor='w').pack(fill='x')
        buttons_bar = tk.Frame(body, bg='#202b30')
        buttons_bar.pack(fill='x', pady=6)
        tk.Button(buttons_bar, text='接受', bg='#5b7c52', fg='white',
                  command=lambda: finish(True)).pack(side='left')
        tk.Button(buttons_bar, text='关闭', command=lambda: finish(False)).pack(side='left', padx=6)

        def click_art(x, y):
            for name, choice in (('accept_Button', True), ('close_Button', False)):
                rect = buttons.get(name)
                if rect and rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                    finish(choice)
                    return

        def finish(choice):
            if self.accept_task_window is not win:
                return
            self.accept_task_window = None
            self.display_request = None
            try:
                win.destroy()
            except tk.TclError:
                pass
            self.runtime.resume(bool(choice))
            self.drive()

        self._accept_task_finish = finish
        win.protocol('WM_DELETE_WINDOW', lambda: finish(False))

    def close_ui(self, result=None):
        self.task_page = None
        choice = result if result in ('yes', 'no') else (self.ui_close_result or 'no')
        if self.ui_window and self.ui_window.winfo_exists():
            self.ui_window.destroy()
        self.ui_window, self.ui_open = None, False
        self.ui_hits, self.ui_buttons, self.ui_button_text = {}, {}, {}
        self.ui_rects = {}
        self.ui_actions, self.ui_base_layer, self.ui_hover, self.ui_info = {}, None, None, None
        self.ui_pressed, self.ui_render_args = None, None
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
        self.drive()

    def key_down(self, event):
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
        win = tk.Toplevel(self.root)
        win.title('任务指引 · 原生 0.2.53')
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
        if self.display_request and self.display_request.kind in ['talk', 'aside', 'airtalk', 'tapscreen', 'button']:
            self.dialogue = None
            self.display_request = None
            self.runtime.resume()
            self.drive()
            return
        if self.runtime.running or self.runtime_error:
            return
        actors = sorted(self.actors(), key=lambda a: (a[2]-self.x)**2+(a[3]-self.y)**2)
        if npc_id is not None:
            actors = [actor for actor in actors if str(actor[0]) == str(npc_id)]
        if sprite_id is not None:
            actors = [actor for actor in actors if str(actor[1]) == str(sprite_id)]
        if not actors or (actors[0][2]-self.x)**2+(actors[0][3]-self.y)**2 > 150**2:
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
        self.advance_main_condition('map', int(mid))
        self.runtime.notify('tomap', map=int(mid))
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
                self.story_motion.set_face(int(p.get('spritetype', 2)), int(p.get('spriteid', 0)),
                                           int(p.get('face', 0)))
        elif kind == 'tempnpc':
            for p in rows:
                self.state.temp_npcs[str(p['npcid'])] = dict(p, map=self.map_id,
                    x=(float(p.get('x', 0))+.5)*self.map.tw,
                    y=(float(p.get('y', 0))+.5)*self.map.th)
        elif kind == 'spritevisible':
            for p in rows:
                if p.get('spritetype') == 1:
                    self.player_visible = bool(p['visible'])
                elif p.get('spritetype') == 7:
                    if str(p['spriteid']) in self.state.temp_npcs:
                        self.state.temp_npcs[str(p['spriteid'])]['visible'] = int(p['visible'])
                else:
                    key = f'{self.map_id}:{p.get("spritetype", 2)}:{p.get("spriteid", 0)}'
                    self.state.visible[key] = bool(p['visible'])
        elif kind == 'screenmove':
            self.begin_camera_move(parameter)
        elif kind == 'tomap':
            self.request_map(parameter['exit'])
        elif kind == 'areamapmove':
            self.state.world_focus = int(parameter['map'])
        elif kind == 'trialride':
            self.state.trial_ride = int(parameter['rideid'])
        elif kind == 'save':
            self.save()
        elif kind in ['screen', 'screenclose', 'screenflash', 'mainuivisible', 'addteachnode', 'closeui']:
            if kind in ['screen', 'screenclose']:
                self.screen_black = kind == 'screenclose' or parameter.get('type') == 0
            elif kind == 'screenflash':
                self.flash_until = time.monotonic()+.2
            elif kind == 'mainuivisible':
                self.main_ui_visible = bool(parameter.get('visible', 1))
            elif kind == 'addteachnode':
                self.teach_nodes.append(parameter)
            elif kind == 'closeui':
                if getattr(self, 'story_window', None) and self.story_window.winfo_exists():
                    self.story_window.destroy()
        else:
            raise PendingMechanic(f'原画面指令 {kind} 未实现')

    def on_click(self, event):
        if getattr(self, 'task_page', None):
            self.task_page_event('press', event)
            return
        if self.battle and self.battle_ui:
            action = self.battle_ui.click(event.x, event.y)
            if action == 'finish':
                self.finish_battle()
            return
        if self.display_request and self.display_request.kind == 'button':
            # Original tutorial buttons wait for the highlighted node itself;
            # a click on empty ground must not dismiss both hide/restore tips.
            if self.main_ui_visible and not self.ui_open and self.scene_ui.click(event.x, event.y):
                self.advance_button_tip()
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

    def advance_button_tip(self):
        if not self.display_request or self.display_request.kind != 'button':
            return
        self.display_request = None
        self.dialogue = None
        self.runtime.resume()
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
            return
        if not self.state.pets:
            raise PendingMechanic('原战斗要求至少一只宠物，当前队伍为空')
        if not any(p.hp > 0 for p in self.state.pets):
            raise PendingMechanic('队伍已全灭；原版恢复点/白屏传送尚未接入，不能伪造复活')
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
        self.battle, self.battle_ui = battle, BattleUI(self, battle)
        battle.source_id = str(npcid)
        self.battle_tips = []
        self.keys.clear()
        self.dialogue = None
        self.event_issue = ''
        self.player_sprite = self.state.sprite_id
        if battle.kind == 'wild':
            self.runtime.notify('fight', type=1)
            self.drive()

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
        self.state.active_pet = min(battle.player_index, max(0, len(self.state.pets)-1))
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
        if getattr(self, 'camera_action', None):
            return
        if getattr(getattr(self, 'story_motion', None), 'actions', []):
            return
        if self.display_request or self.runtime_error:
            return
        if self.battle and not self.runtime.running:
            return
        if self.pending_wait or self.ui_open:
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
                    if request.kind == 'aside':
                        self.dialogue = '旁白:'+self.dialogue
                    return
                if request.kind in ['button', 'tapscreen']:
                    text = request.data.get('text') or '\n'.join(request.data.get('texts', []))
                    if self.battle:
                        if text:
                            self.battle.messages.append(text.strip())
                            self.battle_tips.append(text.strip())
                        self.runtime.resume()
                        continue
                    self.display_request = request
                    self.dialogue = text or '点击继续'
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
                    self.start_battle(npcid, kind={3: 'arena', 4: 'budokan', 5: 'infinite_arena'}.get(fight_type))
                    self.runtime.resume('start')
                    self.drive()
                    return
                if request.kind == 'battleover':
                    if not self.battle:
                        raise PendingMechanic('缺少实际战斗结果，不能代填胜负；请读取战斗前存档')
                    return
                if request.kind == 'openui':
                    self.open_ui(request)
                    return
                if request.kind == 'closeui':
                    self.close_ui()
                    return
                if request.kind == 'accepttask':
                    self.accept_task_ui(request)
                    return
                if request.kind == 'wait':
                    parameters = request.data.get('parameters', {})
                    wait_type = int(parameters.get('type', 0) or 0)
                    if self.battle:
                        self.pending_wait = request
                        return
                    if wait_type == 2 and self.ui_open:
                        self.pending_wait = request
                        return
                    if wait_type == 3:
                        self.pending_wait = request
                        self.event_issue = '等待原版场景障碍/骑乘交互；点击继续可恢复剧情'
                        return
                    self.runtime.resume()
                    continue
                self.apply_visual(request)
                if self.camera_action or getattr(getattr(self, 'story_motion', None), 'actions', []):
                    return
                self.runtime.resume()
                self.player_sprite = self.state.sprite_id
            except (PendingMechanic, NotImplementedError, ValueError, KeyError) as error:
                self.runtime_error = f'{self.runtime.file}：{error}'
                self.state.audit.append({'event': self.runtime.file, 'index': self.runtime.index, 'pending': str(error)})
                return

    def battle_action_complete(self):
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
        for obj in self.map.objects:
            if obj['group'] != 'eventLayer':
                continue
            left, top = float(obj.get('x', 0)), float(obj.get('y', 0))
            width, height = float(obj.get('width', 64)), float(obj.get('height', 64))
            if not (left <= x < left+width and top <= y < top+height):
                continue
            area = int(obj['name'])
            self.inside_areas = {str(area)}
            if not self.runtime.running:
                self.runtime.notify('toarea', area=area)
            self.advance_main_condition('area', area)
            # getAreaSpriteAtTileCoord returns the first matching area.
            return

    def tick(self):
        now = time.monotonic()
        elapsed = max(0.0, now-self._play_clock)
        self._play_clock = now
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
            self.state.activities['play_seconds'] = (
                float(self.state.activities.get('play_seconds', 0))+elapsed)
        if self.battle and self.battle_ui:
            self.battle_ui.advance(seconds=elapsed)
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
        self.event_issue = self.runtime_error
        guide_note = ''
        if self.guide.target:
            guide_note = f' | 指引：{self.guide.target.label}'
            if self.guide.active:
                guide_note += f'（自动前往，剩余 {max(0, len(self.guide.route)-1)} 张地图）'
            elif self.guide.message:
                guide_note += f'（{self.guide.message}）'
        self.status.set(self.runtime_error or ('方向键/WASD移动 · 空格/E对话 · F5保存 · F9读取 · G指引'
                                               ' | 原剧情状态机、战斗核心与原版战斗UI已接入' + guide_note))

    def make_frame(self):
        if self.battle and self.battle_ui:
            return self.battle_ui.render()
        original_dialogue = self.dialogue
        self.dialogue = None
        try:
            frame = super().make_frame()
        finally:
            self.dialogue = original_dialogue
        if getattr(self, 'screen_black', False):
            frame.paste('#101010', (0, 0, self.WIDTH, self.HEIGHT))
        elif self.main_ui_visible:
            self.scene_ui.render(frame)
        if original_dialogue is None:
            self._draw_chest_fx(frame)
            self._draw_obstacle_fx(frame)
        if original_dialogue is not None:
            name, sep, content = original_dialogue.partition(':')
            if not sep:
                name, content = '', original_dialogue
            is_player = name in ['尼尔', '皮尔']
            portrait = next((r['icon'] for r in self.data.tables['Npc'].values() if r['name'] == name), None)
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
        if time.monotonic() < getattr(self, 'flash_until', 0):
            frame = Image.blend(frame, Image.new('RGBA', frame.size, 'white'), .7)
        if getattr(self, 'task_page', None):
            frame.alpha_composite(self.task_page.render().resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS))
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

    def save(self):
        if self.booting:
            return False
        if self.battle:
            self.event_issue = '战斗中存档尚未接入原版战斗快照，未写入不一致的进度。'
            return False
        try:
            self.state.map_id, self.state.x, self.state.y = self.map_id, self.x, self.y
            self.state.presentation = {
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
            self.repair_legacy_obstacle_coordinates(state)
            runtime = EventRuntime(self.data, state)
            runtime.restore(state.pending_runtime)
            self.close_transient_ui()
            self.state, self.runtime = state, runtime
            self.guide.rebind(state)
            self.load_map(state.map_id, state.x, state.y)
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
            self._play_clock = time.monotonic()
            self.drive()
            return True
        except (ValueError, KeyError, OSError) as error:
            messagebox.showerror('未覆盖原存档', str(error), parent=self.root)
            return False

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
        if (int(self.state.presentation.get('sprite_collision_version', 0)) >= 2 or self.runtime.running
                or not hasattr(self.map, 'sprite_blocked')):
            return
        mounts = Mounts(self.state)
        if not self.map.sprite_blocked(self.x, self.y, mounts):
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
                self.state.audit.append({'repair': 'legacy-player-inside-sprite-mask',
                                         'map': self.map_id, 'before': origin, 'after': [px, py]})
                return
            for neighbor in ((x, y+1), (x-1, y), (x+1, y), (x, y-1)):
                if (neighbor not in visited and 0 <= neighbor[0] < self.map.width
                        and 0 <= neighbor[1] < self.map.height):
                    visited.add(neighbor)
                    queue.append(neighbor)

    def close_transient_ui(self):
        self.task_page = None
        # Loading must not acknowledge an old event through close_ui().
        if self.ui_window and self.ui_window.winfo_exists():
            self.ui_window.destroy()
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
        win = tk.Toplevel(self.root)
        win.title(title)
        box = tk.Text(win, width=68, height=25, wrap='word', font=('Microsoft YaHei UI', 11))
        box.pack(fill='both', expand=True)
        box.insert('1.0', content)
        box.config(state='disabled')
        return win

    def show_reward(self, title, items):
        """Open the original GetItemUI for a real reward list."""
        if not items:
            return
        if self.ui_open:
            self.event_issue = title + '：' + '、'.join(
                f'{self.data.tables["Item"].get(str(key), self.data.tables["Pet"].get(str(key), self.data.tables["Money"].get(str(key), {}))).get("name", key)} × {count}'
                for key, count in items)
            return
        self.open_ui(Request('openui', 'get-item', 1, {
            'parameters': {'uiid': 49, 'title': title, 'items': list(items)}}))

    def _get_item_body(self, body, info):
        parameters = self.ui_parameters
        title = str(parameters.get('title', '获得物品'))
        items = list(parameters.get('items', []))
        if getattr(self, 'ui_art_label', None) is not None:
            layer = self.cocos_ui.render('GetItemUI', (800, 480), {'title_Text': title})
            photo = ImageTk.PhotoImage(layer)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
        frame = tk.Frame(self.ui_window, bg='#202b30', highlightthickness=0)
        rect = self.ui_hits.get('item_ListView') or self.ui_rects.get('item_ListView')
        if rect:
            frame.place(x=rect[0], y=rect[1], width=max(120, rect[2]-rect[0]),
                        height=max(100, rect[3]-rect[1]))
            frame.lift()
        else:
            frame.pack(fill='both', expand=True)
        box = tk.Listbox(frame, width=36, height=7, font=('Microsoft YaHei UI', 10),
                         bg='#182125', fg='#e8d8b8', selectbackground='#49606a')
        box.pack(fill='both', expand=True)
        for key, count in items:
            row = (self.data.tables['Item'].get(str(key))
                   or self.data.tables['Pet'].get(str(key))
                   or self.data.tables['Money'].get(str(key), {}))
            box.insert('end', f'{row.get("name", key)} × {count}')
        info.set(f'{title}：{len(items)} 项奖励')
        self.ui_actions['confirm_Button'] = self.close_ui
        self.ui_actions['close_Button'] = self.close_ui

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
            self.start_battle(npcid, kind={3: 'arena', 4: 'budokan', 5: 'infinite_arena'}.get(fight_type))
            self.runtime.resume('start')
            self.drive()
        def no():
            self.close_ui()
            self.runtime.resume('no')
            self.drive()
        self.ui_actions['confirm_Button'] = yes
        self.ui_actions['cancel_Button'] = no
        self.ui_actions['close_Button'] = no

    def open_skill_replace(self, uid, key, scroll=None):
        passive = str(key) in self.data.tables['Talent']
        self.open_ui(Request('openui', 'skill-replace', 1, {
            'parameters': {'uiid': 54, 'uid': uid, 'key': str(key),
                           'passive': passive, 'scroll': scroll}}))

    def _skill_replace_body(self, body, info):
        parameters = self.ui_parameters
        uid = parameters.get('uid')
        if uid is None and self.state.pets:
            uid = self.state.pets[0].uid
        uid = str(uid)
        key = parameters.get('key')
        if key is None:
            key = next(iter(self.data.tables['Skill']))
        key = str(key)
        passive = bool(parameters.get('passive'))
        scroll = parameters.get('scroll')
        pet = next((candidate for candidate in self.state.pets
                    if str(candidate.uid) == uid), None)
        if pet is None:
            info.set('这只宠物不在携带栏。')
            return
        table = 'Talent' if passive else 'Skill'
        keys = ([str(value) for value in pet.talents if 400200 <= int(value) < 400300]
                if passive else [str(value) for value in pet.skills])
        new_row = self.data.tables[table].get(key, {})
        if getattr(self, 'ui_art_label', None) is not None:
            layer = self.cocos_ui.render('SkillReplaceUI', (800, 480), {
                'petName_Text': self.data.tables['Pet'][str(pet.species)]['name'],
                'info_Text': f'新技能：{new_row.get("name", key)}',
                'mySkillInfo_Text': '选择要替换掉的技能；确认后消耗卷轴/货币。'})
            photo = ImageTk.PhotoImage(layer)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
        frame = tk.Frame(self.ui_window, bg='#202b30')
        rect = self.ui_hits.get('skill_ListView') or self.ui_rects.get('skill_ListView')
        if rect:
            frame.place(x=rect[0], y=rect[1], width=max(180, rect[2]-rect[0]),
                        height=max(120, rect[3]-rect[1]))
            frame.lift()
        else:
            frame.pack(fill='both', expand=True)
        box = tk.Listbox(frame, font=('Microsoft YaHei UI', 10), exportselection=False)
        box.pack(fill='both', expand=True)
        for index, current in enumerate(keys):
            row = self.data.tables[table].get(str(current), {})
            box.insert('end', f'{index+1}. {row.get("name", current)}')
        if not keys:
            info.set('没有可替换的技能槽。')
        else:
            box.selection_set(0)
            info.set(f'新技能：{new_row.get("name", key)} · 请选择替换槽')
        def confirm():
            if not box.curselection():
                info.set('请选择要替换的技能。')
                return
            try:
                self.state.learn_skill(pet.uid, key, scroll=scroll,
                                       replace=box.curselection()[0])
            except (ValueError, KeyError) as error:
                info.set(str(error))
                return
            self.close_ui()
        self.ui_actions['confirm_Button'] = confirm
        self.ui_actions['close_Button'] = self.close_ui

    def _open_chest_body(self, body, info):
        key_count = self.state.count('240001')
        text = f'开启宝箱需要钥匙 ×1（持有 {key_count}）'
        if getattr(self, 'ui_art_label', None) is not None:
            layer = self.cocos_ui.render('OpenChestConfirmUI', (800, 480), {
                'title_Text': '开启宝箱', 'need_BitmapFontLabel': str(key_count)})
            photo = ImageTk.PhotoImage(layer)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
        info.set(text)
        def confirm():
            try:
                rewards = self.state.open_chest_item()
            except (ValueError, KeyError) as error:
                info.set(str(error))
                return
            self.close_ui()
            self.show_reward('宝箱获得', rewards)
        self.ui_actions['confirm_Button'] = confirm
        self.ui_actions['cancel_Button'] = self.close_ui
        self.ui_actions['close_Button'] = self.close_ui

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
        from activities import Activities
        from game_state import numbers
        index = int(self.ui_parameters.get('index', 0) or 0)
        activity = Activities(self.state)
        egg = self.state.activities.get('eggs', {}).get(str(index))
        tables = self.data.tables
        if not egg:
            info.set('这个孵化位是空的。')
            self.ui_actions['takeBackEgg_Button'] = lambda: info.set('这个孵化位是空的。')
            self.ui_actions['hatch_Button'] = lambda: info.set('这个孵化位是空的。')
            self.ui_actions['moneyHatch_Button'] = lambda: info.set('这个孵化位是空的。')
            self.ui_actions['close_Button'] = self._close_hatch_check
            return
        row = tables['HatchItem'][egg['item']]
        item_name = tables['Item'].get(str(egg['item']), {}).get('name', str(egg['item']))
        lines = [f'{index+1} 号孵化位 · {item_name}']
        if egg.get('pet'):
            target = tables['Pet'].get(str(egg['pet']['species']), {})
            lines.append(f'已孵化：{target.get("name", egg["pet"]["species"])}，等待领取')
        else:
            lines.append(f'孵化经验 {egg["exp"]} / {row["exp"]}')
            item_ids = [str(v) for v in numbers(row.get('itemIds', ''))]
            item_counts = [int(v) for v in numbers(row.get('itemCounts', ''))]
            for item_id, count in zip(item_ids, item_counts):
                have = self.state.count(item_id)
                lines.append(f'{tables["Item"].get(item_id, {}).get("name", item_id)} {have} / {count}')
            money = tables['Money'].get(str(row.get('moneyId')), {})
            lines.append(f'金币孵化 {row.get("moneyCount", 0)} {money.get("name", "")}')
        if getattr(self, 'ui_art_label', None) is not None:
            layer = self.cocos_ui.render('HatchCheckUI', (800, 480), {
                'cost_BitmapFontLabel': str(row.get('moneyCount', 0))})
            photo = ImageTk.PhotoImage(layer)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
        frame = tk.Frame(self.ui_window, bg='#202b30', highlightthickness=0)
        rect = self.ui_hits.get('condition_ListView') or self.ui_rects.get('condition_ListView')
        if rect:
            frame.place(x=rect[0], y=rect[1], width=max(160, rect[2]-rect[0]),
                        height=max(90, rect[3]-rect[1]))
            frame.lift()
        else:
            frame.pack(fill='both', expand=True)
        box = tk.Listbox(frame, font=('Microsoft YaHei UI', 9), exportselection=False,
                         bg='#182125', fg='#e8d8b8', selectbackground='#49606a')
        box.pack(fill='both', expand=True)
        for line in lines:
            box.insert('end', line)
        info.set(' · '.join(lines))
        def back():
            self.close_ui()
            self.open_ui(Request('openui', 'hatch-room', 1, {
                'parameters': {'uiid': 5}}))
        def take():
            try:
                activity.take_egg(index)
            except (ValueError, KeyError) as error:
                info.set(str(error))
                return
            back()
        def hatch(use_money=False):
            try:
                activity.hatch(index, use_money=use_money)
            except (ValueError, KeyError) as error:
                info.set(str(error))
                return
            back()
        self.ui_actions['takeBackEgg_Button'] = take
        self.ui_actions['hatch_Button'] = lambda: hatch(False)
        self.ui_actions['moneyHatch_Button'] = lambda: hatch(True)
        self.ui_actions['close_Button'] = back
        self.ui_window.bind('<Escape>', lambda _event: back())

    def _close_hatch_check(self):
        self.close_ui()

    def open_evolution(self, uid, back=47):
        self.open_ui(Request('openui', 'evolution-condition', 1, {
            'parameters': {'uiid': 61, 'uid': uid, 'back': back}}))

    def _evolution_body(self, body, info):
        from game_state import numbers
        parameters = self.ui_parameters
        uid = str(parameters.get('uid') or
                  (self.state.pets[0].uid if self.state.pets else ''))
        back_uiid = int(parameters.get('back', 47) or 47)
        pet = next((candidate for candidate in self.state.pets
                    if str(candidate.uid) == uid), None)
        if pet is None:
            info.set('这只宠物不在携带栏。')
            return
        tables = self.data.tables
        pet_name = tables['Pet'][pet.species]['name']
        evolution = tables['Evolution'].get(str(pet.species))
        target = tables['Pet'].get(str(evolution['petId'])) if evolution else None
        if not evolution or not target:
            info.set(f'{pet_name} 没有可用的原版进化路线。')
            self.ui_actions['evolution_Button'] = lambda: info.set('没有可用的原版进化路线。')
            self.ui_actions['close_Button'] = self.close_ui
            return
        need_level = int(evolution.get('level', 1) or 1)
        item_ids = [str(v) for v in numbers(evolution.get('itemIds', ''))]
        item_counts = [int(v) for v in numbers(evolution.get('itemCounts', ''))]
        lines = [f'等级 {pet.level} / {need_level}',
                 f'进化为 {target["name"]}']
        for item_id, count in zip(item_ids, item_counts):
            row = tables['Item'].get(item_id, {})
            have = self.state.count(item_id)
            lines.append(f'{row.get("name", item_id)} {have} / {count}')
        if getattr(self, 'ui_art_label', None) is not None:
            layer = self.cocos_ui.render('EvolutionConditionUI', (800, 480), {
                'petName_Text': f'{pet_name} → {target["name"]}',
                'cost_BitmapFontLabel': str(len(item_ids))})
            photo = ImageTk.PhotoImage(layer)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
        frame = tk.Frame(self.ui_window, bg='#202b30', highlightthickness=0)
        rect = self.ui_hits.get('condition_ListView') or self.ui_rects.get('condition_ListView')
        if rect:
            frame.place(x=rect[0], y=rect[1], width=max(150, rect[2]-rect[0]),
                        height=max(90, rect[3]-rect[1]))
            frame.lift()
        else:
            frame.pack(fill='both', expand=True)
        box = tk.Listbox(frame, font=('Microsoft YaHei UI', 9), exportselection=False,
                         bg='#182125', fg='#e8d8b8', selectbackground='#49606a')
        box.pack(fill='both', expand=True)
        for line in lines:
            box.insert('end', line)
        info.set(f'{pet_name} → {target["name"]} · ' + ' · '.join(lines))
        def back():
            self.close_ui()
            if back_uiid == 57 and pet in self.state.pets:
                self.open_pet_property(pet.uid)
            else:
                self.pets_ui()
        def confirm():
            try:
                self.state.evolve(pet.uid)
            except (ValueError, KeyError) as error:
                info.set(str(error))
                return
            back()
        self.ui_actions['evolution_Button'] = confirm
        self.ui_actions['close_Button'] = back
        self.ui_window.bind('<Escape>', lambda _event: back())

    def open_skill_learn_confirm(self, uid, key, scroll=None, replace=None, back=None):
        self.open_ui(Request('openui', 'skill-learn-confirm', 1, {
            'parameters': {'uiid': 60, 'uid': uid, 'key': str(key),
                           'scroll': scroll, 'replace': replace, 'back': back}}))

    def _skill_learn_confirm_body(self, body, info):
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
            layer = self.cocos_ui.render('SkillLearnConfirmUI', (800, 480), {
                'petName_Text': name, 'lv_BitmapFontLabel': str(pet.level),
                'skillName_Text': str(row['name']),
                'skillInfoTitle_Text': '技能学习确认',
                'info_Text': text,
                'cost_BitmapFontLabel': str(row.get('moneyCount', 1) if scroll is None else 1),
                'energy_Text': str(row.get('energy', '')),
                'energy_BitmapFontLabel': str(row.get('energy', ''))})
            photo = ImageTk.PhotoImage(layer)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
        info.set(text)
        def back():
            self.close_ui()
            if back_uiid:
                self.open_ui(Request('openui', 'skill-learn', 1, {
                    'parameters': {'uiid': 6}}))
        def confirm():
            try:
                self.state.learn_skill(pet.uid, key, scroll=scroll, replace=replace)
            except (ValueError, KeyError) as error:
                info.set(str(error))
                return
            back()
        self.ui_actions['confirm_Button'] = confirm
        self.ui_actions['close_Button'] = back
        self.ui_window.bind('<Escape>', lambda _event: back())

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
        uid = str(self.ui_parameters.get('uid') or
                  (self.state.pets[-1].uid if self.state.pets else ''))
        back = self.ui_parameters.get('back')
        pet = next((candidate for candidate in self.state.pets
                    if str(candidate.uid) == uid), None)
        if pet is None:
            info.set('抽宠记录不在携带栏。')
            return
        stats = pet.stats(self.data.tables)
        name = self.data.tables['Pet'][pet.species]['name']
        if getattr(self, 'ui_art_label', None) is not None:
            layer = self.cocos_ui.render('LuckyDrawPetInfoUI', (800, 480), {
                'name_Text': name,
                'arrtLife_BitmapFontLabel': str(stats[0]),
                'arrtEnergy_BitmapFontLabel': str(stats[1]),
                'arrtStrength_BitmapFontLabel': str(stats[2]),
                'arrtDefense_BitmapFontLabel': str(stats[3]),
                'arrtSpeed_BitmapFontLabel': str(stats[4])})
            photo = ImageTk.PhotoImage(layer)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
        info.set(f'抽到 {name} Lv.{pet.level} · 生命 {stats[0]} / 能量 {stats[1]} / '
                 f'攻击 {stats[2]} / 防御 {stats[3]} / 速度 {stats[4]}')
        def finish():
            self.close_ui()
            if back == 'lottery':
                self.lottery_ui(force=True)
        self.ui_actions['confirm_Button'] = finish
        self.ui_actions['weixin_Button'] = finish
        self.ui_actions['close_Button'] = finish

    def open_pet_property(self, uid):
        self.open_ui(Request('openui', 'pet-property', 1, {
            'parameters': {'uiid': 57, 'uid': uid}}))

    def _pet_property_body(self, body, info):
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

    def _illustrated_overview_body(self, body, info):
            """Original IllustratedUI: original cards in item_ScrollView."""
            tables = self.state.tables
            current = [1]
            species = []
            scroll = [0]
            selected = [0]
            rect = self.ui_hits.get('item_ScrollView') or self.ui_rects.get('item_ScrollView')
            if not rect:
                rect = (64, 93, 719, 421)
            body.pack_forget()

            def card_visible(key, row):
                stars = max(0, min(5, int(row.get('starLevel', 0) or 0)))
                values = {}
                for index in range(1, 6):
                    values[f'star_Image_{index}'] = index <= stars
                    values[f'star_Image_{index}_black'] = False
                values['star_Panel'] = True
                values['star_black_Panel'] = False
                return values

            def paint():
                kind = current[0]
                found = sum(1 for key in species if key in self.state.encyclopedia)
                layer = self.cocos_ui.render('IllustratedUI', (800, 480), {
                    'findedCount_BitmapFontLabel': str(len(self.state.encyclopedia)),
                    'progress_BitmapFontLabel': f'{found}/{len(species)}',
                })
                base_hits = dict(self.cocos_ui.hits)
                base_rects = dict(self.cocos_ui.rects)
                base_buttons = dict(self.cocos_ui.buttons)
                base_text = dict(self.cocos_ui.button_text)
                draw = ImageDraw.Draw(layer)
                start = scroll[0]
                for index, key in enumerate(species[start:start+15]):
                    row = tables['Pet'][key]
                    resource = f'PetHead/head_{row.get("filePath", "")}.png'
                    card = self.cocos_ui.render(
                        'IllustratedItemUI', (180, 60),
                        {'itemName_Text': row['name'],
                         'id_BitmapFontLabel': str(key)},
                        resources={'head_Image': resource},
                        visible=card_visible(key, row))
                    column, line = index % 3, index // 3
                    x = round(rect[0] + 10 + column * 210)
                    y = round(rect[1] + 8 + line * 64)
                    layer.alpha_composite(card, (x, y))
                    self.ui_hits[f'illustrated_card_{index}'] = (x, y, x+180, y+60)
                    if start + index == selected[0]:
                        draw.rectangle((x+1, y+1, x+178, y+58),
                                       outline='#ffe36e', width=2)
                self.ui_base_layer = layer
                self.ui_hits.update(base_hits)
                self.ui_rects = base_rects
                self.ui_buttons = base_buttons
                self.ui_button_text = base_text
                for index in range(15):
                    self.ui_actions[f'illustrated_card_{index}'] = (
                        lambda value=index: open_card(scroll[0]+value))
                if hasattr(self, 'ui_art_label') and self.ui_art_label.winfo_exists():
                    photo = ImageTk.PhotoImage(layer)
                    self.ui_art_label.configure(image=photo)
                    self.ui_art_label.image = photo

            def open_card(index):
                if not 0 <= index < len(species):
                    return
                selected[0] = index
                key = species[index]
                row = tables['Pet'][key]
                info.set(f'{row["name"]}（{key}） · '
                         f'{"已收录" if key in self.state.encyclopedia else "未收录"}')
                paint()
                self.open_ui(Request('openui', 'illustrated-pet', 1, {
                    'parameters': {'uiid': 8, 'species': key}}))

            def tab(kind):
                nonlocal species
                current[0] = kind
                selected[0] = 0
                scroll[0] = 0
                species = sorted((key for key, row in tables['Pet'].items()
                                  if str(row.get('kind', '')) == str(kind)),
                                 key=lambda value: int(value))
                info.set(f'{tables["PetKindEnum"].get(str(kind), {}).get("name", kind)} · '
                         f'已收录 {sum(1 for key in species if key in self.state.encyclopedia)}/'
                         f'{len(species)}')
                paint()

            def wheel(event):
                step = -3 if event.delta > 0 else 3
                top = max(0, len(species)-15)
                scroll[0] = min(top, max(0, scroll[0]+step))
                paint()

            for kind in range(1, 6):
                self.ui_actions[f'tag_{kind}_Button'] = lambda value=kind: tab(value)
            self.ui_actions['close_Button'] = self.close_ui
            if hasattr(self, 'ui_art_label'):
                self.ui_art_label.bind('<MouseWheel>', wheel)
            tab(1)

    def pets_ui(self):
        if self.battle:
            self.event_issue = '请在战斗界面使用换宠和道具指令。'
            return
        self.open_ui(Request('openui', 'pet-list', 1, {'parameters': {'uiid': 47}}))

    def _pet_list_body(self, body, info):
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
                            {'parameters': {'uiid': 1}}))

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

    def _bag_body(self, body, info):
        """Original BagUI: five tabs, item list, use and fragment synthesis."""
        tabs = {1: ('道具', {1, 2, 3}), 2: ('蛋', {5}), 3: ('卷轴', {6}),
                4: ('重要', {4, 7}), 5: ('碎片', {8})}
        state, tables = self.state, self.data.tables
        current = [1]
        selected = [None]
        scroll = [0]
        targets = list(state.pets)
        target_name = tk.StringVar()
        target_box = ttk.Combobox(body, textvariable=target_name, state='readonly',
                                  values=[f'{tables["Pet"][p.species]["name"]} Lv.{p.level}'
                                          for p in targets], width=30)
        target_box.pack(anchor='w', pady=2)
        if targets:
            target_box.current(0)
            preferred = getattr(self, 'bag_target_uid', None)
            match = next((i for i, pet in enumerate(targets) if pet.uid == preferred), None)
            if match is not None:
                target_box.current(match)
        list_frame = tk.Frame(self.ui_window, bg='#202b30', highlightthickness=0)
        rect = self.ui_hits.get('item_ListView') or self.ui_rects.get('item_ListView')
        if rect:
            list_frame.place(x=rect[0], y=rect[1], width=max(120, rect[2]-rect[0]),
                             height=max(100, rect[3]-rect[1]))
            list_frame.lift()
        else:
            list_frame.pack(fill='both', expand=True)
        box = tk.Listbox(list_frame, width=38, height=13, font=('Microsoft YaHei UI', 9),
                         bg='#182125', fg='#e8d8b8', selectbackground='#49606a')
        bar = tk.Scrollbar(list_frame, command=box.yview)
        box.configure(yscrollcommand=bar.set)
        box.pack(side='left', fill='both', expand=True)
        bar.pack(side='right', fill='y')
        rows = []

        def paint():
            nonlocal rows
            # BagUI is an 800x480 original page.  Keep its art as the whole
            # page and draw original BagListItemUI rows in item_ListView;
            # never place a host Listbox over the original tabs/info panel.
            layer = self.cocos_ui.render('BagUI', (800, 480),
                                         {'info_Text': info.get(),
                                          'Layer/root_Panel/badge_ProjectNode/Layer/root_Panel/goldCount_BitmapFontLabel':
                                              str(self.state.count('700002')),
                                          'Layer/root_Panel/gold_ProjectNode/Layer/root_Panel/goldCount_BitmapFontLabel':
                                              str(self.state.count('700001'))},
                                         resources={
                                             'Layer/root_Panel/badge_ProjectNode/Layer/root_Panel/icon_Sprite':
                                                 'UI/money_little_icon_badge.png',
                                             'Layer/root_Panel/gold_ProjectNode/Layer/root_Panel/icon_Sprite':
                                                 'UI/money_little_icon_gold.png',
                                         },
                                         positions={'info_Text': [190, 150.4]})
            self.ui_base_layer = layer
            self.ui_hits = dict(self.cocos_ui.hits)
            self.ui_rects = dict(self.cocos_ui.rects)
            self.ui_buttons = dict(self.cocos_ui.buttons)
            self.ui_button_text = dict(self.cocos_ui.button_text)
            if rect:
                for index, (item_id, row, count) in enumerate(
                        rows[scroll[0]:scroll[0]+3]):
                    item_index = scroll[0]+index
                    row_layer = self.cocos_ui.render(
                        'BagListItemUI', (300, 89),
                        {'itemName_Text': row['name'],
                         'itemCount_BitmapFontLabel': f'X{count}'},
                        resources={'icon_Image': f'ItemIcon/{row.get("texture", "")}'},
                        visible={'selected_Image': bool(
                            selected[0] and selected[0][0] == item_id)})
                    layer.alpha_composite(row_layer, (round(rect[0]), round(rect[1]+index*89)))
                    self.ui_hits[f'bag_row_{index}'] = (
                        rect[0], rect[1]+index*89, rect[0]+300, rect[1]+(index+1)*89)
            if hasattr(self, 'ui_art_label') and self.ui_art_label.winfo_exists():
                photo = ImageTk.PhotoImage(layer)
                self.ui_art_label.configure(image=photo)
                self.ui_art_label.image = photo

        def refresh(_=None):
            rows.clear()
            scroll[0] = 0
            box.delete(0, 'end')
            allowed = tabs[current[0]][1]
            for item_id, count in state.inventory.items():
                if int(count) <= 0:
                    continue
                row = tables['Item'].get(str(item_id))
                if not row or int(row.get('type', -1)) not in allowed:
                    continue
                rows.append((str(item_id), row, int(count)))
                box.insert('end', f'{row["name"]} × {count}  — {row.get("des", "")}')
            info.set(f'{tabs[current[0]][0]} · {len(rows)} 种 · 金币 {state.count("700001")}')
            if rows:
                box.selection_set(0)
                show()
            paint()

        def show(_=None):
            if not rows or not box.curselection():
                return
            item_id, row, count = rows[box.curselection()[0]]
            selected[0] = (item_id, row, count)
            debris = tables.get('DebrisItem', {}).get(item_id)
            synth = (f' · 碎片合成需要 {debris["needCount"]} 个' if debris else '')
            info.set(f'{row["name"]} × {count}{synth}\n{row.get("des", "")}')
            paint()

        def use():
            entry = selected[0]
            if not entry:
                info.set('请先选择道具。')
                return
            try:
                if entry[0] == '210001':
                    self.open_ui(Request('openui', 'open-chest', 1, {
                        'parameters': {'uiid': 55}}))
                    return
                target = targets[target_box.current()] if target_box.current() >= 0 else None
                message = state.use_item(entry[0], target)
                info.set(message)
                refresh()
            except ValueError as error:
                info.set(str(error))
                paint()

        def synthesize():
            entry = selected[0]
            if not entry:
                info.set('请先选择碎片。')
                return
            item_id, row, count = entry
            debris = tables.get('DebrisItem', {}).get(item_id)
            if not debris:
                info.set('这个道具不是可合成碎片。')
                return
            need = int(debris['needCount'])
            if count < need:
                info.set(f'碎片不足：需要 {need} 个，当前 {count} 个。')
                return
            try:
                with state.transaction():
                    state.consume([item_id], [need])
                    state.grant(debris['petId'], 1)
                refresh()
                info.set(f'合成成功：{tables["Pet"][debris["petId"]]["name"]} 已进入宠物栏。')
            except (ValueError, KeyError) as error:
                info.set(str(error))

        def tab(value):
            current[0] = value
            selected[0] = None
            refresh()

        def choose_row(index):
            if not 0 <= index < len(rows):
                return
            box.selection_clear(0, 'end')
            box.selection_set(index)
            show()

        def wheel(event):
            step = -1 if event.delta > 0 else 1
            top = max(0, len(rows)-3)
            scroll[0] = min(top, max(0, scroll[0]+step))
            paint()

        for index in range(1, 6):
            self.ui_actions[f'tag_{index}_Button'] = (
                lambda value=index: tab(value))
        for index in range(3):
            self.ui_actions[f'bag_row_{index}'] = (
                lambda value=index: choose_row(scroll[0]+value))
        self.ui_actions['use_Button'] = use
        self.ui_actions['heCheng_Button'] = synthesize
        self.ui_actions['bag_use'] = use
        self.ui_actions['bag_synthesize'] = synthesize
        self.ui_actions['close_Button'] = self.close_ui
        box.bind('<<ListboxSelect>>', show)
        if hasattr(self, 'ui_art_label'):
            self.ui_art_label.bind('<MouseWheel>', wheel)
        refresh()
        # The original BagUI already contains the tabs, list, info panel and
        # action buttons.  Host widgets stay only as hidden state holders.
        body.pack_forget()
        list_frame.place_forget()

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
    app = NativeGame(root, OriginalData(data_root()))
    if args.screenshot:
        app.make_frame().convert('RGB').save(args.screenshot)
        root.after(200, root.destroy)
    if args.smoke_test:
        root.after(1200, root.destroy)
    root.mainloop()


if __name__ == '__main__':
    main()
