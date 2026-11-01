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
from guide import Guide


class NativeGame(ActivityUI, Preview):
    def __init__(self, root, data):
        self.state = GameState(data.tables)
        self.cocos_ui = CocosUI(data)
        self.runtime = EventRuntime(data, self.state)
        self.booting = True
        self.runtime_error = ''
        self.display_request = None
        self.wait_until = 0
        self.camera_focus = None
        self.player_visible = True
        self.player_sprite = self.state.sprite_id
        self.inside_areas = set()
        self.battle = None
        self.battle_ui = None
        self.battle_tips = []
        self.pending_wait = None
        self.ui_window = None
        self.ui_open = False
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
        super().__init__(root, data)
        self.booting = False
        self.canvas.bind('<Button-1>', self.on_click)
        root.title('口袋妖怪 · 原生 PC 移植开发版 0.2.29（全系统还原进行中）')
        top = root.winfo_children()[0]
        for child in top.winfo_children():
            child.destroy()
        tk.Label(top, text='口袋妖怪 · PC 移植开发版', fg='#f5d492', bg='#202b30',
                 font=('Microsoft YaHei UI', 12, 'bold')).pack(side='left', padx=14, pady=10)
        for label, callback in [('宠物', self.pets_ui), ('背包', self.bag_ui), ('任务', self.tasks_ui),
                                ('指引', self.guide_ui), ('抽宠', self.lottery_ui),
                                ('坐骑', self.mounts_ui), ('宝藏', self.treasure_ui),
                                ('赛跑', self.running_pet_ui),
                                ('签到', self.login_ui), ('每日', self.daily_ui),
                                ('图鉴', self.illustrated_ui),
                                ('成就', self.achievements_ui),
                                ('保存', self.save), ('读取', self.restore), ('当前进度', self.about)]:
            ttk.Button(top, text=label, command=callback).pack(side='left', padx=3)
        default_save = Path(os.environ.get('LOCALAPPDATA', str(Path.home())))/'PocketNativePC'
        self.save_path = Path(os.environ.get('POCKET_NATIVE_SAVE_DIR', str(default_save)))/'slot1.json'
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
            self.inside_areas = set()
            self.encounter_distance, self.encounter_threshold = 0.0, 0

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
            self.background = self.map.render(self.SCALE)

    def break_obstacle(self, obs_type, tx, ty):
        """Break/cut an obsType sprite only when the current ride has the ability."""
        mounts = Mounts(self.state)
        if not mounts.obstacle_ability(obs_type):
            return False
        if self.map.remove_obstacle(tx, ty) is None:
            return False
        self.state.removed_obstacles.append([int(self.map_id), int(tx), int(ty), int(obs_type)])
        self.background = self.map.render(self.SCALE)
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
        return super().actor_animation(oid, sid)

    def _draw_chest_fx(self, frame):
        fx = getattr(self, 'chest_fx', None)
        if not fx:
            return frame
        focus = getattr(self, 'camera_focus', None) or (self.x, self.y)
        camx = max(0, min(focus[0]*self.SCALE-self.WIDTH/2,
                          self.background.width-self.WIDTH))
        camy = max(0, min(focus[1]*self.SCALE-self.HEIGHT/2,
                          self.background.height-self.HEIGHT))
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
        focus = getattr(self, 'camera_focus', None) or (self.x, self.y)
        camx = max(0, min(focus[0]*self.SCALE-self.WIDTH/2,
                          self.background.width-self.WIDTH))
        camy = max(0, min(focus[1]*self.SCALE-self.HEIGHT/2,
                          self.background.height-self.HEIGHT))
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
        53: ('GoodsBuyConfirmUI', '购买确认'),
        54: ('SkillReplaceUI', '技能替换'),
        55: ('OpenChestConfirmUI', '开启宝箱'),
        56: ('FreePetConfirmUI', '放生确认'),
    }

    def open_ui(self, request):
        parameters = request.data.get('parameters', {})
        self.ui_parameters = parameters
        uiid = int(parameters.get('uiid', 0) or 0)
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
            tk.Button(body, text='治疗全部宠物', bg='#5b7c52', fg='white',
                      command=cure).pack(pady=6)
        elif uiid == 14:
            info.set('保存当前游戏进度。')
            def save_now():
                self.save()
                info.set(self.event_issue or '进度已保存。')
            self.ui_actions['confirm_Button'] = save_now
            tk.Button(body, text='保存进度', command=save_now).pack(pady=6)
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
        elif uiid == 44:
            self._daily_body(body, info)
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
        self.shop_uiid = uiid
        clerk = {1: '1', 2: '3', 3: '4'}.get(uiid)
        if clerk:
            talks = dict(self.state.activities.get('shop_talks', {}))
            talks[clerk] = int(talks.get(clerk, 0))+1
            self.state.activities['shop_talks'] = talks
        goods = []
        for key, row in sorted(self.data.tables[table].items(), key=lambda pair: int(pair[0])):
            if str(row.get('repeat', '1')) == '0' and self.state.shop_purchases.get(f'{table}:{key}'):
                continue
            goods.append((str(key), row))
        info.set(f'商店共 {len(goods)} 件商品 · 持有金币 {self.state.count("700001")} · 双击商品查看原版详情')
        frame = tk.Frame(self.ui_window, bg='#202b30')
        rect = self.ui_hits.get('goods_ListView') or self.ui_rects.get('goods_ListView')
        if rect:
            frame.place(x=rect[0], y=rect[1], width=max(220, rect[2]-rect[0]),
                        height=max(120, rect[3]-rect[1]))
            frame.lift()
        else:
            frame = tk.Frame(body, bg='#202b30')
            frame.pack(fill='both', expand=True)
        box = tk.Listbox(frame, width=58, height=6, font=('Microsoft YaHei UI', 10))
        box.pack(side='left', fill='both', expand=True)
        for key, row in goods:
            currency = self.data.tables['Money'].get(str(row['moneyType']), {}).get('name', row['moneyType'])
            box.insert('end', f'{row["name"]}  {row["price"]} {currency}  — {row.get("des", "")}')
        def detail(event=None):
            if not box.curselection():
                return
            key, row = goods[box.curselection()[0]]
            self.open_goods_detail(uiid, table, key, row)
        def buy():
            if not box.curselection():
                return
            key, row = goods[box.curselection()[0]]
            try:
                self.state.buy(table, key)
                info.set(f'购买 {row["name"]} 成功 · 剩余 {self.state.count(row["moneyType"])}')
            except (ValueError, KeyError, NotImplementedError) as error:
                info.set(str(error))
        box.bind('<Double-Button-1>', detail)
        tk.Button(frame, text='购买', command=buy).pack(side='left', padx=8, anchor='n')
        tk.Button(frame, text='详情', command=detail).pack(side='left', padx=8, anchor='n')
        self.ui_actions['shop_buy'] = buy
        self.ui_actions['shop_detail'] = detail

    def open_goods_detail(self, shop_uiid, table, key, row):
        self.open_ui(Request('openui', 'shop-goods', 1, {
            'parameters': {'uiid': 52, 'table': table, 'key': key,
                           'shop_uiid': shop_uiid}}))

    def _back_to_shop(self, shop_uiid):
        self.close_ui()
        self.open_ui(Request('openui', 'shop-return', 1, {
            'parameters': {'uiid': shop_uiid}}))

    def render_component(self, name, size=(800, 480), text=None):
        """Render a prefab layout on a full canvas instead of its tiny node size."""
        layout = self.cocos_ui.layout(name)
        root = layout['tree']
        old = root.get('size')
        root['size'] = list(size)
        try:
            return self.cocos_ui.render(name, size, text or {})
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
        if getattr(self, 'ui_art_label', None) is not None:
            base = self.cocos_ui.render('ShopUI', (800, 480), {})
            base_buttons = dict(self.cocos_ui.buttons)
            card = self.cocos_ui.render('ShopGoodsUI', (153, 233), {
                'name_Text': row['name'],
                'cost_BitmapFontLabel': str(row['price']),
                'count_BitmapFontLabel': f'x{row.get("count", 1)}',
            })
            card_buttons = dict(self.cocos_ui.buttons)
            card = card.resize((184, 280), Image.Resampling.LANCZOS)
            base.alpha_composite(card, (320, 90))
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

    def _goods_confirm_body(self, body, info):
        parameters = self.ui_parameters
        table = str(parameters.get('table', 'Shop'))
        key = parameters.get('key')
        if key is None:
            key = sorted(self.data.tables[table].items(), key=lambda pair: int(pair[0]))[0][0]
        key = str(key)
        shop_uiid = int(parameters.get('shop_uiid', 1))
        row = self.data.tables[table][key]
        currency = self.data.tables['Money'].get(str(row['moneyType']), {}).get('name', row['moneyType'])
        text = f'购买 {row["name"]}？\n需要 {row["price"]} {currency}'
        if getattr(self, 'ui_art_label', None) is not None:
            layer = self.cocos_ui.render('GoodsBuyConfirmUI', (800, 480), {'info_Text': text})
            photo = ImageTk.PhotoImage(layer)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
        info.set(text)
        def confirm():
            try:
                self.state.buy(table, key)
            except (ValueError, KeyError, NotImplementedError) as error:
                info.set(str(error))
                return
            self._back_to_shop(shop_uiid)
        self.ui_actions['buy_Button'] = confirm
        self.ui_actions['buy_2_Button'] = confirm
        self.ui_actions['close_Button'] = self.close_ui

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
        elif key not in ['m', 'f3', 'escape']:
            if key in {'up', 'down', 'left', 'right', 'w', 'a', 's', 'd'}:
                self.guide.stop('已停止自动指引。')
            self.keys.add(key)

    def advance_main_condition(self, kind, value):
        TaskProgress(self.state).update(kind, int(value))

    def guide_toggle(self):
        if self.battle:
            return
        if self.guide.active:
            self.guide.stop('已停止自动指引。')
        else:
            target = self.guide.refresh()
            if target:
                self.keys.clear()
                self.guide.start(target)

    def guide_ui(self):
        if self.battle:
            self.event_issue = '战斗中不能自动前往，请先结束战斗。'
            return
        win = tk.Toplevel(self.root)
        win.title('任务指引 · 原生 0.2.29')
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

    def interact(self):
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
            for p in rows:
                if 'x' not in p or 'y' not in p:
                    continue
                x, y = float(p['x'])*64+32, (self.map.height-float(p['y']))*64
                key = f'{self.map_id}:{p.get("spritetype", 2)}:{p.get("spriteid", 0)}'
                if p.get('spritetype') == 1:
                    self.x, self.y = x, y
                elif p.get('spritetype') == 7:
                    row = self.state.temp_npcs.get(str(p['spriteid']))
                    if row:
                        row['x'], row['y'] = x, y
                else:
                    self.state.positions[key] = [x, y]
        elif kind in ['face', 'toface']:
            faces = {1: 'standup', 2: 'standdown', 3: 'standleft', 4: 'standright'}
            for p in rows:
                if p.get('spritetype') == 1 and p.get('face') in faces:
                    self.face = faces[p['face']]
        elif kind == 'tempnpc':
            for p in rows:
                self.state.temp_npcs[str(p['npcid'])] = dict(p, map=self.map_id,
                    x=float(p.get('x', 0))*64+32, y=(self.map.height-float(p.get('y', 0)))*64)
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
            self.camera_focus = None if parameter.get('x', -1) < 0 else (
                float(parameter['x'])*64+32, (self.map.height-float(parameter['y']))*64)
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
        if self.battle and self.battle_ui:
            action = self.battle_ui.click(event.x, event.y)
            if action == 'finish':
                self.finish_battle()
            return
        self.interact()

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

    def drive(self):
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

    def tick(self):
        now = time.monotonic()
        elapsed = max(0.0, now-self._play_clock)
        self._play_clock = now
        if not self.booting:
            self.state.activities['play_seconds'] = (
                float(self.state.activities.get('play_seconds', 0))+elapsed)
        if self.battle and self.battle_ui:
            self.battle_ui.advance()
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
            self.steps = [1] if self.runtime.running or self.runtime_error else []
            self.guide.step()
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
        areas = set()
        for obj in self.map.objects:
            if obj['group'] != 'eventLayer':
                continue
            x, y = float(obj.get('x', 0)), float(obj.get('y', 0))
            w, h = float(obj.get('width', 64)), float(obj.get('height', 64))
            if x <= self.x < x+w and y <= self.y < y+h:
                areas.add(obj['name'])
        if not self.runtime.running:
            for area in areas-self.inside_areas:
                self.advance_main_condition('area', area)
                if self.runtime.notify('toarea', area=int(area)):
                    break
        self.inside_areas = areas
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
                from PIL import Image
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
            from PIL import Image
            frame = Image.blend(frame, Image.new('RGBA', frame.size, 'white'), .7)
        return frame

    def draw_guide(self, frame):
        target = getattr(self.guide, 'target', None)
        if not target or self.runtime.running or self.battle:
            return
        point = self.guide.point()
        if not point:
            return
        focus = self.camera_focus or (self.x, self.y)
        camx = max(0, min(focus[0]*self.SCALE-self.WIDTH/2, self.background.width-self.WIDTH))
        camy = max(0, min(focus[1]*self.SCALE-self.HEIGHT/2, self.background.height-self.HEIGHT))
        sx, sy = point[0]*self.SCALE-camx, point[1]*self.SCALE-camy
        draw = ImageDraw.Draw(frame)
        try:
            font = ImageFont.truetype(str(Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts/msyh.ttc'), 15)
        except OSError:
            font = ImageFont.load_default()
        label = '目标' if self.map_id == target.map_id else '出口'
        if 30 < sx < self.WIDTH-30 and 30 < sy < self.HEIGHT-30:
            draw.ellipse((sx-14, sy-14, sx+14, sy+14), outline='#ffe36e', width=4)
            draw.ellipse((sx-4, sy-4, sx+4, sy+4), fill='#ffe36e')
            draw.rounded_rectangle((sx+18, sy-24, sx+18+len(label)*16+12, sy-2),
                                   radius=5, fill=(35, 40, 32, 210))
            draw.text((sx+24, sy-23), label, font=font, fill='#ffe36e')
        else:
            cx, cy = self.WIDTH/2, self.HEIGHT/2
            angle = math.atan2(sy-cy, sx-cx)
            radius = min(self.WIDTH, self.HEIGHT)*.38
            ax, ay = cx+math.cos(angle)*radius, cy+math.sin(angle)*radius
            draw.line((cx, cy, ax, ay), fill='#ffe36e', width=4)
            wing = 16
            left = (ax-math.cos(angle-.55)*wing, ay-math.sin(angle-.55)*wing)
            right = (ax-math.cos(angle+.55)*wing, ay-math.sin(angle+.55)*wing)
            draw.polygon((ax, ay, left, right), fill='#ffe36e')
            draw.text((ax-18, ay+14), label, font=font, fill='#ffe36e')

    def save(self):
        if self.booting:
            return
        if self.battle:
            self.event_issue = '战斗中存档尚未接入原版战斗快照，未写入不一致的进度。'
            return
        self.state.map_id, self.state.x, self.state.y = self.map_id, self.x, self.y
        self.state.presentation = {
            'face': self.face, 'player_visible': self.player_visible,
            'camera_focus': self.camera_focus, 'main_ui_visible': self.main_ui_visible,
            'teach_nodes': self.teach_nodes, 'screen_black': getattr(self, 'screen_black', False),
            'encounter_distance': self.encounter_distance,
            'encounter_threshold': self.encounter_threshold,
        }
        self.runtime.persist()
        self.state.activities['save_total'] = int(
            self.state.activities.get('save_total', 0))+1
        self.state.save(self.save_path)
        self.event_issue = '已保存独立移植存档，包含当前剧情位置、背包、任务和随机数状态。'

    def restore(self):
        if self.battle:
            self.event_issue = '战斗中暂不支持读取存档，请在战斗结束后读取。'
            return
        if not self.save_path.exists():
            self.event_issue = '还没有原生移植存档。'
            return
        try:
            state = GameState.load(self.data.tables, self.save_path)
            runtime = EventRuntime(self.data, state)
            runtime.restore(state.pending_runtime)
            self.close_transient_ui()
            self.state, self.runtime = state, runtime
            self.guide.rebind(state)
            self.load_map(state.map_id, state.x, state.y)
            self.runtime_error, self.display_request, self.dialogue = '', None, None
            self.pending_wait, self.wait_until = None, 0
            self.camera_focus, self.screen_black, self.flash_until = None, False, 0
            self.player_visible, self.main_ui_visible = True, True
            self.teach_nodes, self.battle_tips = [], []
            for key in ('face', 'player_visible', 'camera_focus', 'main_ui_visible',
                        'teach_nodes', 'screen_black', 'encounter_distance', 'encounter_threshold'):
                if key in state.presentation:
                    setattr(self, key, state.presentation[key])
            self.keys.clear()
            self.player_sprite = state.sprite_id
            self.drive()
        except (ValueError, KeyError, OSError) as error:
            messagebox.showerror('未覆盖原存档', str(error), parent=self.root)

    def close_transient_ui(self):
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

    def open_free_pet(self, uid):
        self.open_ui(Request('openui', 'free-pet', 1, {
            'parameters': {'uiid': 56, 'uid': uid}}))

    def _free_pet_body(self, body, info):
        uid = str(self.ui_parameters.get('uid') or
                  (self.state.pets[0].uid if self.state.pets else ''))
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
            back()
        self.ui_actions['confirm_Button'] = confirm
        self.ui_actions['cancel_Button'] = back
        self.ui_actions['close_Button'] = back

    def illustrated_ui(self):
        if self.battle or self.ui_open:
            return
        self.open_ui(Request('openui', 'illustrated', 1, {'parameters': {'uiid': 48}}))

    def _illustrated_overview_body(self, body, info):
        """Original IllustratedUI: five PetKindEnum tabs over the full Pet table."""
        tables = self.state.tables
        current = [1]
        selected = [0]
        species = []
        frame = tk.Frame(self.ui_window, bg='#202b30', highlightthickness=0)
        rect = self.ui_hits.get('item_ScrollView') or self.ui_rects.get('item_ScrollView')
        if rect:
            frame.place(x=rect[0], y=rect[1], width=max(160, rect[2]-rect[0]),
                        height=max(120, rect[3]-rect[1]))
            frame.lift()
        else:
            frame.pack(fill='both', expand=True)
        box = tk.Listbox(frame, width=58, height=16, font=('Microsoft YaHei UI', 9),
                         bg='#182125', fg='#e8d8b8', selectbackground='#49606a')
        bar = tk.Scrollbar(frame, command=box.yview)
        box.configure(yscrollcommand=bar.set)
        box.pack(side='left', fill='both', expand=True)
        bar.pack(side='right', fill='y')

        def show(_=None):
            if not species:
                return
            if box.curselection():
                selected[0] = box.curselection()[0]
            key = species[selected[0]]
            row = tables['Pet'][key]
            found = '已收录' if key in self.state.encyclopedia else '未收录'
            skills = '、'.join(tables['Skill'].get(str(s), {}).get('name', str(s))
                              for s in str(row.get('skillIds', '')).split(',')[:4] if s and s != '0')
            info.set(f'{row["name"]}（{key}） · {found}\n'
                     f'种族 {tables["PetKindEnum"].get(str(row.get("kind")), {}).get("name", row.get("kind"))} · '
                     f'星级 {row.get("starLevel")} · 最大等级 {row.get("maxLevel")}\n'
                     f'技能：{skills or "无"}')

        def tab(kind):
            nonlocal species
            current[0] = kind
            species = sorted((key for key, row in tables['Pet'].items()
                              if str(row.get('kind', '')) == str(kind)), key=lambda value: int(value))
            box.delete(0, 'end')
            for key in species:
                row = tables['Pet'][key]
                mark = '✓' if key in self.state.encyclopedia else '·'
                box.insert('end', f'{mark} {key}  {row["name"]}  星级 {row.get("starLevel")}')
            found = sum(1 for key in species if key in self.state.encyclopedia)
            info.set(f'{tables["PetKindEnum"].get(str(kind), {}).get("name", kind)} · '
                     f'已收录 {found}/{len(species)}')
            if getattr(self, 'ui_art_label', None) is not None:
                layer = self.cocos_ui.render('IllustratedUI', (800, 480), {
                    'findedCount_BitmapFontLabel': str(len(self.state.encyclopedia)),
                    'progress_BitmapFontLabel': f'{found}/{len(species)}',
                })
                photo = ImageTk.PhotoImage(layer)
                self.ui_art_label.configure(image=photo)
                self.ui_art_label.image = photo
            if species:
                box.selection_set(0)
                selected[0] = 0
                show()

        for kind in range(1, 6):
            self.ui_actions[f'tag_{kind}_Button'] = lambda value=kind: tab(value)
        self.ui_actions['close_Button'] = self.close_ui
        box.bind('<<ListboxSelect>>', show)
        tab(1)

    def pets_ui(self):
        if self.battle:
            self.event_issue = '请在战斗界面使用换宠和道具指令。'
            return
        self.open_ui(Request('openui', 'pet-list', 1, {'parameters': {'uiid': 47}}))

    def _pet_list_body(self, body, info):
        """Original PetListUI: party list, stats/skills/talents, battle and evolve."""
        state, tables = self.state, self.data.tables
        pets = list(state.pets)
        selected = [0 if pets else -1]
        page = ['base']
        confirm_free = [None]
        detail_frame = tk.Frame(self.ui_window, bg='#202b30', highlightthickness=0)
        detail_rect = self.ui_hits.get('baseInfo_Panel') or self.ui_rects.get('baseInfo_Panel')
        if detail_rect:
            detail_frame.place(x=detail_rect[0], y=detail_rect[1],
                               width=max(160, detail_rect[2]-detail_rect[0]),
                               height=max(120, detail_rect[3]-detail_rect[1]))
            detail_frame.lift()
        else:
            detail_frame.pack(fill='both', expand=True)
        detail = tk.Text(detail_frame, width=44, height=13, wrap='word', font=('Microsoft YaHei UI', 9))
        detail.pack(fill='both', expand=True)
        list_frame = tk.Frame(self.ui_window, bg='#202b30', highlightthickness=0)
        rect = self.ui_hits.get('itemListView_Panel') or self.ui_rects.get('itemListView_Panel')
        if rect:
            list_frame.place(x=rect[0], y=rect[1], width=max(150, rect[2]-rect[0]),
                             height=max(120, rect[3]-rect[1]))
            list_frame.lift()
        else:
            list_frame.pack(fill='both', expand=True)
        box = tk.Listbox(list_frame, width=34, height=11, font=('Microsoft YaHei UI', 9),
                         bg='#182125', fg='#e8d8b8', selectbackground='#49606a')
        bar = tk.Scrollbar(list_frame, command=box.yview)
        box.configure(yscrollcommand=bar.set)
        box.pack(side='left', fill='both', expand=True)
        bar.pack(side='right', fill='y')

        def show(_=None):
            if not pets:
                detail.delete('1.0', 'end')
                detail.insert('1.0', '当前没有携带宠物。')
                return
            if box.curselection():
                selected[0] = box.curselection()[0]
            pet = pets[selected[0]]
            row = tables['Pet'][pet.species]
            stats = pet.stats(tables)
            active = ' · 出战中' if selected[0] == state.active_pet else ''
            if page[0] == 'skill':
                skills = [tables['Skill'].get(str(s), {}).get('name', str(s)) for s in pet.skills]
                body_text = '技能：\n' + ('\n'.join(f'· {name}' for name in skills) or '（无）')
            elif page[0] == 'talent':
                talents = [tables['Talent'].get(str(t), {}).get('name', str(t)) for t in pet.talents]
                body_text = '天赋：\n' + ('\n'.join(f'· {name}' for name in talents) or '（无）')
            else:
                body_text = (f'{row["name"]}  Lv.{pet.level}{active}\n'
                             f'生命 {pet.hp}/{stats[0]}  能量 {pet.energy}/{stats[1]}\n'
                             f'力量 {stats[2]}  防御 {stats[3]}  速度 {stats[4]}\n'
                             f'品质 {pet.quality}  突破 {pet.breakthrough}  亲密度 {pet.friendly}\n'
                             f'携带物 {tables["Item"].get(str(pet.held_item), {}).get("name", pet.held_item)}')
            detail.delete('1.0', 'end')
            detail.insert('1.0', body_text)
            info.set(f'{row["name"]} · 出战 {state.active_pet+1}/{max(1, len(pets))}')

        def rebuild():
            nonlocal pets
            pets = list(state.pets)
            box.delete(0, 'end')
            for pet in pets:
                row = tables['Pet'][pet.species]
                mark = '★' if pets.index(pet) == state.active_pet else ' '
                box.insert('end', f'{mark} {row["name"]}  Lv.{pet.level}  '
                                  f'HP {pet.hp}/{pet.stats(tables)[0]}')
            if pets:
                selected[0] = min(selected[0], len(pets)-1)
                box.selection_set(selected[0])
                show()

        def join_battle():
            if not pets:
                return
            state.active_pet = selected[0]
            confirm_free[0] = None
            rebuild()

        def evolve():
            if not pets:
                return
            pet = pets[selected[0]]
            try:
                state.evolve(pet.uid)
                confirm_free[0] = None
                rebuild()
                info.set('进化成功。')
            except (ValueError, KeyError) as error:
                info.set(str(error))

        def free():
            if not pets:
                return
            pet = pets[selected[0]]
            if selected[0] == state.active_pet:
                info.set('出战中宠物不能放生，请先更换出战宠物。')
                return
            self.open_free_pet(pet.uid)

        def use_item():
            if not pets:
                return
            pet = pets[selected[0]]
            self.bag_target_uid = pet.uid
            self.close_ui()
            self.bag_ui()

        def tag(value):
            page[0] = value
            show()

        box.bind('<<ListboxSelect>>', show)
        self.ui_actions.update({
            'joinBattle_Button': join_battle,
            'evolution_Button': evolve,
            'useItem_Button': use_item,
            'free_Button': free,
            'skillTag_Button': lambda: tag('skill'),
            'talentTag_Button': lambda: tag('talent'),
            'skill_Button': lambda: tag('skill'),
            'trainValue_Button': lambda: tag('base'),
            'close_Button': self.close_ui,
        })
        rebuild()

    def bag_ui(self):
        if self.battle:
            self.event_issue = '请在战斗界面使用道具指令。'
            return
        self.open_ui(Request('openui', 'bag', 1, {'parameters': {'uiid': 46}}))

    def _bag_body(self, body, info):
        """Original BagUI: five tabs, item list, use and fragment synthesis."""
        tabs = {1: ('道具', {1, 3, 4, 6}), 2: ('蛋', {5}), 3: ('卷轴', {2}),
                4: ('重要', {7}), 5: ('碎片', {8})}
        state, tables = self.state, self.data.tables
        current = [1]
        selected = [None]
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

        def refresh(_=None):
            rows.clear()
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

        def show(_=None):
            if not rows or not box.curselection():
                return
            item_id, row, count = rows[box.curselection()[0]]
            selected[0] = (item_id, row, count)
            debris = tables.get('DebrisItem', {}).get(item_id)
            synth = (f' · 碎片合成需要 {debris["needCount"]} 个' if debris else '')
            info.set(f'{row["name"]} × {count}{synth}\n{row.get("des", "")}')

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

        for index in range(1, 6):
            self.ui_actions[f'tag_{index}_Button'] = (
                lambda value=index: tab(value))
        self.ui_actions['use_Button'] = use
        self.ui_actions['heCheng_Button'] = synthesize
        self.ui_actions['bag_use'] = use
        self.ui_actions['bag_synthesize'] = synthesize
        self.ui_actions['close_Button'] = self.close_ui
        box.bind('<<ListboxSelect>>', show)
        refresh()
        tk.Button(body, text='使用', command=use).pack(side='left', padx=6)
        tk.Button(body, text='碎片合成', command=synthesize).pack(side='left', padx=6)

    def tasks_ui(self):
        row = self.data.tables['MainTask'][str(self.state.main_task)]
        TaskProgress(self.state).update()
        labels = {2: '未接取', 3: '进行中', 4: '可提交', 5: '已完成'}
        lines = [f'主线：{row["name"]} · {labels.get(self.state.main_state, self.state.main_state)}', row['des'],
                 f'进度 {self.state.task_counts.get(f"main:{self.state.main_task}", [])} / {row["counts"]}', '', '支线任务：']
        for key, status in sorted(self.state.branch_states.items(), key=lambda pair: int(pair[0])):
            if status not in (3, 4):
                continue
            branch = self.data.tables['BranchTask'][key]
            lines.extend([f'{branch["name"]} · {labels[status]}', branch['des'],
                          f'进度 {self.state.task_counts.get(f"branch:{key}", [])} / {branch["counts"]}', ''])
        lines.extend([f'已完成主线：{len(self.state.completed_main)}', f'已完成支线：{len(self.state.completed_branch)}'])
        self.listing('任务', '\n'.join(lines))

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
            'parameters': {'uiid': 51, 'text': text}}))


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
