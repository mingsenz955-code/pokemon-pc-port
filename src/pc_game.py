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
from event_runtime import EventRuntime, PendingMechanic
from csb_render import CocosUI
from battle import make_npc_battle, make_wild_battle
from arena import ArenaProgress, make_arena_battle
from infinite_arena import InfiniteArenaProgress, make_infinite_arena_battle
from budokan import BudokanProgress, make_budokan_battle
from battle_ui import BattleUI
from activity_ui import ActivityUI
from daily_tasks import DailyTasks
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
        self.show_map_label = False
        self.data = data
        self.guide = Guide(self)
        self.ui_hits = {}
        self.ui_buttons = {}
        self.ui_button_text = {}
        self.ui_actions = {}
        self.ui_base_layer = None
        self.ui_hover = None
        self.ui_pressed = None
        self.ui_render_args = None
        self.ui_close_result = None
        self.ui_info = None
        self.arena_summary = None
        self.chest_fx = None
        self.running_session = None
        self.running_result = None
        self.running_race_token = None
        super().__init__(root, data)
        self.booting = False
        self.canvas.bind('<Button-1>', self.on_click)
        root.title('口袋妖怪 · 原生 PC 移植开发版 0.2.10（全系统还原进行中）')
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
    }

    def open_ui(self, request):
        parameters = request.data.get('parameters', {})
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
            self.ui_hits, self.ui_buttons, self.ui_button_text = {}, {}, {}
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
        goods = []
        for key, row in sorted(self.data.tables[table].items(), key=lambda pair: int(pair[0])):
            if str(row.get('repeat', '1')) == '0' and self.state.shop_purchases.get(f'{table}:{key}'):
                continue
            goods.append((str(key), row))
        info.set(f'商店共 {len(goods)} 件商品 · 持有金币 {self.state.count("700001")}')
        frame = tk.Frame(body, bg='#202b30')
        frame.pack(fill='both', expand=True)
        box = tk.Listbox(frame, width=58, height=6, font=('Microsoft YaHei UI', 10))
        box.pack(side='left', fill='both', expand=True)
        for key, row in goods:
            currency = self.data.tables['Money'].get(str(row['moneyType']), {}).get('name', row['moneyType'])
            box.insert('end', f'{row["name"]}  {row["price"]} {currency}  — {row.get("des", "")}')
        def buy():
            if not box.curselection():
                return
            key, row = goods[box.curselection()[0]]
            try:
                self.state.buy(table, key)
                info.set(f'购买 {row["name"]} 成功 · 剩余 {self.state.count(row["moneyType"])}')
            except (ValueError, KeyError, NotImplementedError) as error:
                info.set(str(error))
        tk.Button(frame, text='购买', command=buy).pack(side='left', padx=8, anchor='n')

    def heal_party(self):
        self.state.cure_party()

    def close_ui(self, result=None):
        choice = result if result in ('yes', 'no') else (self.ui_close_result or 'no')
        if self.ui_window and self.ui_window.winfo_exists():
            self.ui_window.destroy()
        self.ui_window, self.ui_open = None, False
        self.ui_hits, self.ui_buttons, self.ui_button_text = {}, {}, {}
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
        win.title('任务指引 · 原生 0.2.10')
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
                self.event_issue = f'宝藏获得：{row.get("name", item_id)} × {count}'
            except (ValueError, KeyError) as error:
                self.event_issue = str(error)
            return
        if str(actors[0][1]) == '30001':
            from activities import Activities
            try:
                rewards = Activities(self.state).open_village_chest(oid)
                names = []
                for key, count in rewards:
                    row = (self.data.tables['Item'].get(str(key)) or self.data.tables['Pet'].get(str(key))
                           or self.data.tables['Money'].get(str(key), {}))
                    names.append(f'{row.get("name", key)} × {count}')
                self.event_issue = '宝箱获得：'+'、'.join(names)
            except (ValueError, KeyError) as error:
                self.event_issue = str(error)
            return
        self.advance_main_condition('talk', oid)
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
        if result == 'caught':
            pet = battle.caught_pet
            land = int(self.data.tables['Pet'][pet.species].get('kind', -1))
            TaskProgress(self.state).update('catch', int(pet.species), land, self.state.map_id)
            DailyTasks(self.state).record('catch')
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
                        if not messagebox.askyesno('战斗确认', '要开始这场战斗吗？', parent=self.root):
                            self.runtime.resume('no')
                            continue
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
                    self.display_request = request
                    key = str(request.data['parameters']['btask'])
                    row = self.data.tables['BranchTask'][key]
                    result = messagebox.askyesno(row['name'], row['des'], parent=self.root)
                    self.display_request = None
                    self.runtime.resume(result)
                    continue
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
        if self.battle and self.battle_ui:
            self.battle_ui.advance()
        if getattr(self, 'chest_fx', None):
            self.chest_fx['age'] += 1
            if self.chest_fx['age'] >= 26:
                self.chest_fx = None
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
                             {'parameters': {'uiid': 44}}))

    def listing(self, title, content):
        win = tk.Toplevel(self.root)
        win.title(title)
        box = tk.Text(win, width=68, height=25, wrap='word', font=('Microsoft YaHei UI', 11))
        box.pack(fill='both', expand=True)
        box.insert('1.0', content)
        box.config(state='disabled')
        return win

    def pets_ui(self):
        if self.battle:
            self.event_issue = '请在战斗界面使用换宠和道具指令。'
            return
        win = tk.Toplevel(self.root)
        win.title('携带宠物 · 原生 0.2')
        win.transient(self.root)
        frame = tk.Frame(win)
        frame.pack(fill='both', expand=True, padx=8, pady=8)
        box = tk.Listbox(frame, width=32, height=12, font=('Microsoft YaHei UI', 10))
        box.pack(side='left', fill='both', expand=True)
        detail = tk.Text(frame, width=44, height=12, wrap='word', font=('Microsoft YaHei UI', 10))
        detail.pack(side='left', fill='both', expand=True, padx=(8, 0))
        pets = list(self.state.pets)
        for p in pets:
            row = self.data.tables['Pet'][p.species]
            box.insert('end', f'{row["name"]}  Lv.{p.level}  HP {p.hp}/{p.stats(self.data.tables)[0]}')
        def show(_=None):
            if not box.curselection():
                return
            p = pets[box.curselection()[0]]
            row = self.data.tables['Pet'][p.species]
            stats = p.stats(self.data.tables)
            detail.delete('1.0', 'end')
            detail.insert('1.0',
                f'{row["name"]}  Lv.{p.level}\n生命 {p.hp}/{stats[0]}  能量 {p.energy}/{stats[1]}\n'
                f'力量 {stats[2]}  防御 {stats[3]}  速度 {stats[4]}\n'
                f'品质 {p.quality}  突破 {p.breakthrough}  亲密度 {p.friendly}\n'
                f'携带物 {p.held_item}\n技能：' + ', '.join(self.data.tables['Skill'][s]['name'] for s in p.skills) + '\n'
                f'天赋：' + ', '.join(self.data.tables['Talent'].get(str(t), {}).get('name', str(t)) for t in p.talents))
        box.bind('<<ListboxSelect>>', show)
        def evolve():
            if not box.curselection():
                return
            p = pets[box.curselection()[0]]
            try:
                self.state.evolve(p.uid)
                detail.delete('1.0', 'end')
                detail.insert('1.0', f'进化为 {self.data.tables["Pet"][p.species]["name"]}！')
                win.destroy()
                self.pets_ui()
            except (ValueError, KeyError) as error:
                detail.delete('1.0', 'end')
                detail.insert('1.0', str(error))
        buttons = tk.Frame(win)
        buttons.pack(fill='x', padx=8, pady=(0, 8))
        tk.Button(buttons, text='尝试进化', command=evolve).pack(side='left')
        tk.Button(buttons, text='关闭', command=win.destroy).pack(side='right')

    def bag_ui(self):
        if self.battle:
            self.event_issue = '请在战斗界面使用道具指令。'
            return
        win = tk.Toplevel(self.root)
        win.title('背包与货币 · 原生 0.2')
        win.transient(self.root)
        info = tk.StringVar(value=f'金币 {self.state.count("700001")}')
        tk.Label(win, textvariable=info, anchor='w', font=('Microsoft YaHei UI', 11)).pack(fill='x', padx=8, pady=4)
        targets = list(self.state.pets)
        target_box = ttk.Combobox(win, state='readonly', width=45,
            values=[f'{self.data.tables["Pet"][p.species]["name"]} Lv.{p.level}' for p in targets])
        target_box.pack(fill='x', padx=8, pady=4)
        if targets:
            target_box.current(0)
        frame = tk.Frame(win)
        frame.pack(fill='both', expand=True, padx=8)
        box = tk.Listbox(frame, width=64, height=14, font=('Microsoft YaHei UI', 10))
        box.pack(side='left', fill='both', expand=True)
        usable = []
        for item_id, count in self.state.inventory.items():
            if count <= 0:
                continue
            row = self.data.tables['Item'].get(str(item_id))
            if row:
                box.insert('end', f'{row["name"]} × {count}  — {row.get("des", "")}')
                if int(row.get('useType', 0)) in (1, 2):
                    usable.append((str(item_id), row))
            else:
                money = self.data.tables['Money'].get(str(item_id), {})
                box.insert('end', f'{money.get("name", item_id)} × {count}')
        def use():
            if not box.curselection():
                return
            index = box.curselection()[0]
            if not usable:
                info.set('没有可使用的回复道具。')
                return
            # The list also contains non-usable rows, so match by a parallel scan.
            selected_text = box.get(index)
            entry = next((entry for entry in usable if selected_text.startswith(entry[1]['name']+' ×')), None)
            if entry is None:
                info.set('这个道具不能在背包中使用。')
                return
            try:
                target = targets[target_box.current()] if target_box.current() >= 0 else None
                message = self.state.use_item(entry[0], target)
                info.set(message + f' · 金币 {self.state.count("700001")}')
                win.destroy()
                self.bag_ui()
            except ValueError as error:
                info.set(str(error))
        tk.Button(frame, text='对所选宠物使用', command=use).pack(side='left', padx=8, anchor='n')
        tk.Button(frame, text='关闭', command=win.destroy).pack(side='left', padx=4, anchor='n')

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
        messagebox.showinfo('当前范围', '原生开发版 0.2，尚未完成所有内容。\n\n'
            '已接入：真实冠军赛序章与主线 1–6、461 条触发规则、任务与事件条件、分支解释器、'
            '原版战斗核心（伤害/属性克制/暴击/状态/捕捉/经验/掉落）、原版 Cocos 战斗界面、'
            '初始宠物选择、任务目标解析与跨图自动指引、商店/治疗/地图等界面入口、独立持久化。\n\n'
            '15 个独立数值函数已与原二进制进行 3,000 组比较。\n'
            '仍在移植：全部 57 种状态、天赋/携带物完整结算、宠物图鉴/融合、完整背包与任务 UI、'
            '战斗内存档、全部支线与结局。遇到缺失机制会停在原位置，不伪造结果。',
            parent=self.root)


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
