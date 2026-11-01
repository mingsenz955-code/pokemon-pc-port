"""Native host for the original-state runtime. Incomplete mechanics stop explicitly."""
from __future__ import annotations

import argparse
import json
import os
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import ImageTk

from original_data import OriginalData
from pc_preview import Preview, data_root
from game_state import GameState
from event_runtime import EventRuntime, PendingMechanic
from csb_render import CocosUI
from battle import make_npc_battle, make_wild_battle
from battle_ui import BattleUI
from activity_ui import ActivityUI
from task_progress import TaskProgress


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
        super().__init__(root, data)
        self.booting = False
        self.canvas.bind('<Button-1>', self.on_click)
        root.title('口袋妖怪 · 原生 PC 移植开发版 0.2（全系统还原进行中）')
        top = root.winfo_children()[0]
        for child in top.winfo_children():
            child.destroy()
        tk.Label(top, text='口袋妖怪 · PC 移植开发版', fg='#f5d492', bg='#202b30',
                 font=('Microsoft YaHei UI', 12, 'bold')).pack(side='left', padx=14, pady=10)
        for label, callback in [('宠物', self.pets_ui), ('背包', self.bag_ui), ('任务', self.tasks_ui), ('抽宠', self.lottery_ui),
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
        return result

    def actor_animation(self, oid, sid):
        if str(sid) == '30001' and hasattr(self, 'state'):
            return 'opened' if str(oid) in self.state.activities.get('village_chests', []) else 'closed'
        return super().actor_animation(oid, sid)

    UI_LAYOUTS = {
        1: ('ShopUI', '商店'), 2: ('EvolutionShopUI', '材料商店'), 3: ('SkillShopUI', '卷轴商店'),
        4: ('PetBankUI', '宠物银行'), 5: ('HatchRoomUI', '孵化屋'), 6: ('SkillLearnUI', '技能学习'),
        7: ('ChoiceFirstPetUI', '初始宠物'), 8: ('IllustratedPetInfoUI', '宠物图鉴'),
        9: ('AreaMapUI', '地区地图'), 10: ('ArenaInfoUI', '竞技场'),
        11: ('CureConfirmUI', '宠物治疗'), 12: ('ContinuousLoginUI', '连续登录'),
        13: ('TrialPetUI', '宠物使者'), 14: ('SaveConfirmUI', '保存进度'),
        15: ('TrialTowerUI', '试炼塔'), 16: ('BuyPetUI', '坐骑商店'),
        17: ('BuyPetUI', '宠物商店'), 18: ('MergePetUI', '宠物融合'),
        19: ('InfiniteArenaUI', '无限竞技场'), 20: ('InfiniteArenaEnterConfirmUI', '无限竞技场入场'),
        21: ('InfiniteArenaQuitConfirmUI', '无限竞技场退出'), 22: ('InfiniteArenaShopUI', '竞技场商店'),
        23: ('PetTuPoUI', '宠物突破'), 24: ('TreasureMapUI', '神秘宝藏'),
        25: ('RunningPetWelUI', '赛宠嘉年华'), 26: ('RankUI', '排行榜'),
        27: ('GiftBagUI', '礼包'), 28: ('MedalShopUI', '奖牌兑换'),
        29: ('RouletteUI', '幸运轮盘'), 30: ('CardLegendUI', '卡牌传说'),
        34: ('PetHeTiUI', '宠物合体'), 36: ('StoreGiftBagUI', '商店礼包'),
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
        try:
            layer = self.cocos_ui.render(layout, (800, 480), {})
            photo = ImageTk.PhotoImage(layer)
            label = tk.Label(win, image=photo, bg='#101418')
            label.image = photo
            label.pack()
            self.ui_art_label = label
        except (FileNotFoundError, ValueError, KeyError) as error:
            tk.Label(win, text=f'原 UI 布局读取失败：{error}', fg='#ffb0a0',
                     bg='#202b30').pack(padx=20, pady=20)
        body = tk.Frame(win, bg='#202b30')
        body.pack(fill='both', expand=True, padx=12, pady=8)
        info = tk.StringVar()
        tk.Label(body, textvariable=info, bg='#202b30', fg='#f2e7cf',
                 font=('Microsoft YaHei UI', 10), justify='left').pack(anchor='w')
        if uiid == 11:
            currency, cost = self.state.cure_cost()
            info.set(f'治疗全部携带宠物：{cost} {self.data.tables["Money"][currency]["name"]}' if currency else '医疗卡治疗免费。')
            def cure():
                try:
                    self.heal_party()
                    info.set('全部携带宠物已恢复。')
                except ValueError as error:
                    info.set(str(error))
            tk.Button(body, text='治疗全部宠物', bg='#5b7c52', fg='white',
                      command=cure).pack(pady=6)
        elif uiid == 14:
            info.set('保存当前游戏进度。')
            tk.Button(body, text='保存进度', command=lambda: (self.save(), info.set(self.event_issue))).pack(pady=6)
        elif uiid == 4:
            self._bank_body(body, info)
        elif uiid == 6:
            self._skill_body(body, info)
        elif uiid == 5:
            self._hatch_body(body, info)
        elif uiid == 17:
            self._pet_shop_body(body, info, parameters.get('par1'))
        elif uiid in (1, 2, 3, 22, 28):
            self._shop_body(body, info, uiid)
        elif uiid == 29:
            self._roulette_body(body, info)
        elif uiid == 30:
            self._cards_body(body, info)
        elif uiid == 9:
            info.set('当前地图：'+self.map.info['name']+f'\n世界焦点：{self.state.world_focus}\n'
                     '原版地区地图会显示已发现城镇和道路。')
        elif uiid == 23:
            self._breakthrough_body(body, info)
        elif uiid == 34:
            info.set('合体需要原版配方中的两只宠物与合体材料。')
        else:
            info.set(f'{name}的交互尚未实现，当前仅显示原版布局。')
        tk.Button(body, text='关闭', command=self.close_ui).pack(side='bottom', pady=6)

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

    def close_ui(self):
        if self.ui_window and self.ui_window.winfo_exists():
            self.ui_window.destroy()
        self.ui_window, self.ui_open = None, False
        if self.pending_wait:
            self.pending_wait = None
            self.runtime.resume()
        elif self.runtime.pending and self.runtime.pending.kind in ('openui', 'closeui'):
            self.runtime.resume()
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
        elif key not in ['m', 'f3', 'escape']:
            self.keys.add(key)

    def advance_main_condition(self, kind, value):
        TaskProgress(self.state).update(kind, int(value))

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
        x = float(obj.get('x', 0))+float(obj.get('width', 64))/2
        y = float(obj.get('y', 0))+float(obj.get('height', 64))/2
        offsets = {'1': (0, -64), '2': (0, 64), '3': (-64, 0), '4': (64, 0)}
        dx, dy = offsets.get(obj['props'].get('face'), (0, 0))
        self.load_map(mid, x+dx, y+dy)
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
        if result in ('win', 'caught'):
            battle.apply_rewards(self.state)
        if result == 'caught':
            pet = battle.caught_pet
            land = int(self.data.tables['Pet'][pet.species].get('kind', -1))
            TaskProgress(self.state).update('catch', int(pet.species), land, self.state.map_id)
        elif result == 'win' and battle.kind != 'wild':
            TaskProgress(self.state).update('fight', 2, 1, int(battle.source_id), -1)
            self.state.npc_fights[battle.source_id] = 1
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
                    self.start_battle(npcid)
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
        old_map, old_x, old_y = self.map_id, self.x, self.y
        if not self.booting:
            TaskProgress(self.state).update()
            self.drive()
            self.steps = [1] if self.runtime.running or self.runtime_error else []
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
            self.status.set('战斗中：点击右侧指令选择技能/道具/换宠/逃跑 · 原版技能与状态数据')
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
        self.status.set(self.runtime_error or '方向键/WASD移动 · 空格/E对话 · F5保存 · F9读取 | 原剧情状态机、战斗核心与原版战斗UI已接入')

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
        if time.monotonic() < getattr(self, 'flash_until', 0):
            from PIL import Image
            frame = Image.blend(frame, Image.new('RGBA', frame.size, 'white'), .7)
        return frame

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
            '已接入：真实冠军赛序章与主线 1–4、461 条触发规则、任务与事件条件、分支解释器、'
            '原版战斗核心（伤害/属性克制/暴击/状态/捕捉/经验/掉落）、原版 Cocos 战斗界面、'
            '初始宠物选择、商店/治疗/地图等界面入口、独立持久化。\n\n'
            '15 个独立数值函数已与原二进制进行 3,000 组比较。\n'
            '仍在移植：全部 57 种状态、天赋/携带物完整结算、地图随机遇敌、宠物图鉴/训练/进化/'
            '突破/融合、完整背包与任务 UI、战斗内存档。遇到缺失机制会停在原位置，不伪造结果。',
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
