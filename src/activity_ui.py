"""Interactive native controls for recovered economy/activity systems."""
import tkinter as tk
from PIL import ImageTk
from activities import Activities
from arena import ArenaProgress
from infinite_arena import InfiniteArenaProgress
from treasure import TreasureHunt


class ActivityUI:
    def _hatch_body(self, body, info):
        from tkinter import ttk
        activity = Activities(self.state)
        slots = tk.Listbox(body, width=70, height=5, exportselection=False)
        slots.pack(fill='x')
        eggs = ttk.Combobox(body, state='readonly', width=65)
        eggs.pack(fill='x')
        available = []
        def refresh():
            selected = slots.curselection()
            slots.delete(0, 'end')
            for index in range(10):
                egg = self.state.activities.get('eggs', {}).get(str(index))
                text = '空位'
                if egg:
                    row = self.data.tables['HatchItem'][egg['item']]
                    text = f'{self.data.tables["Item"][egg["item"]]["name"]} · 经验 {egg["exp"]}/{row["exp"]}'
                    if egg['pet']:
                        text = f'{self.data.tables["Pet"][egg["pet"]["species"]]["name"]} · 已孵化，待领取'
                slots.insert('end', f'{index+1}. {text}')
            if selected:
                slots.selection_set(selected[0])
            available[:] = [k for k in self.data.tables['HatchItem'] if self.state.count(k)]
            eggs['values'] = [f'{self.data.tables["Item"][k]["name"]} × {self.state.count(k)}' for k in available]
            if available:
                eggs.current(0)
            else:
                eggs.set('')
            info.set('选择孵化位；战斗获得孵化经验，可用材料孵化或支付金币直接孵化。')
        def act(kind):
            if not slots.curselection():
                info.set('请先选择孵化位。')
                return
            index = slots.curselection()[0]
            try:
                if kind == 'put':
                    if eggs.current() < 0:
                        raise ValueError('没有可放入的宠物蛋。')
                    activity.put_egg(index, available[eggs.current()])
                elif kind == 'take':
                    activity.take_egg(index)
                else:
                    activity.hatch(index, use_money=kind == 'money')
                refresh()
            except (ValueError, KeyError) as error:
                info.set(str(error))
        def describe(event=None):
            if not slots.curselection():
                return
            egg = self.state.activities.get('eggs', {}).get(str(slots.curselection()[0]))
            if egg and not egg['pet']:
                row = self.data.tables['HatchItem'][egg['item']]
                info.set(f'经验 {egg["exp"]}/{row["exp"]} · 所需材料 {row["itemIds"]} × {row["itemCounts"]}'
                         + f' · 直接孵化 {row["moneyCount"]} {self.data.tables["Money"][row["moneyId"]]["name"]}')
        slots.bind('<<ListboxSelect>>', describe)
        controls = tk.Frame(body)
        controls.pack()
        for title, kind in [('放入宠物蛋', 'put'), ('材料孵化', 'normal'), ('金币孵化', 'money'), ('取回蛋／领取宠物', 'take')]:
            tk.Button(controls, text=title, command=lambda k=kind: act(k)).pack(side='left', padx=3, pady=4)
        self.ui_actions['putIn_Button'] = lambda: act('put')
        self.ui_actions['takeBackEgg_Button'] = lambda: act('take')
        self.ui_actions['takeBack_Button'] = lambda: act('take')
        self.ui_actions['hatch_Button'] = lambda: act('normal')
        self.ui_actions['moneyHatch_Button'] = lambda: act('money')
        self.ui_actions['check_Button'] = lambda: act('take')
        refresh()

    def _skill_body(self, body, info):
        from tkinter import ttk
        from game_state import numbers
        pets = list(self.state.pets)
        if not pets:
            info.set('没有携带的宠物。')
            return
        chooser = ttk.Combobox(body, state='readonly', width=55,
                               values=[f'{self.data.tables["Pet"][p.species]["name"]} Lv.{p.level}' for p in pets])
        chooser.pack(fill='x')
        chooser.current(0)
        box = tk.Listbox(body, width=70, height=6, exportselection=False)
        box.pack(fill='x')
        replacement = ttk.Combobox(body, state='readonly', width=55)
        replacement.pack(fill='x')
        choices = []
        def refresh(event=None):
            pet = pets[chooser.current()]
            choices.clear()
            box.delete(0, 'end')
            for key in numbers(self.data.tables['Pet'][pet.species]['skillIds']):
                skill = self.data.tables['Skill'][str(key)]
                currency = self.data.tables['Money'][skill['moneyId']]['name']
                choices.append((str(key), None))
                box.insert('end', f'{skill["name"]} · {skill["moneyCount"]} {currency}'
                           + (' · 已学会' if str(key) in pet.skills else ''))
            for item, row in self.data.tables['SkillItem'].items():
                key = str(row['skillId'])
                skill = self.data.tables['Skill'].get(key) or self.data.tables['Talent'].get(key)
                if self.state.count(item) and skill:
                    choices.append((key, item))
                    box.insert('end', f'{skill["name"]} · 卷轴 ×1（持有 {self.state.count(item)}）')
            select_skill()
            info.set('主动技能四槽、后天被动技能两槽；已满时需选择替换位置。')
        def select_skill(event=None):
            pet = pets[chooser.current()]
            passive = bool(box.curselection() and choices[box.curselection()[0]][0] in self.data.tables['Talent'])
            keys = [str(k) for k in pet.talents if 400200 <= int(k) < 400300] if passive else pet.skills
            table = self.data.tables['Talent' if passive else 'Skill']
            replacement['values'] = ['增加技能（有空位时）']+[f'替换：{table[str(k)]["name"]}' for k in keys]
            replacement.current(0)
        def learn():
            if not box.curselection():
                return
            key, scroll = choices[box.curselection()[0]]
            try:
                self.state.learn_skill(pets[chooser.current()].uid, key, scroll=scroll,
                                      replace=replacement.current()-1 if replacement.current() else None)
                refresh()
                skill = self.data.tables['Skill'].get(key) or self.data.tables['Talent'][key]
                info.set(f'已学会 {skill["name"]}。')
            except (ValueError, KeyError) as error:
                info.set(str(error))
        chooser.bind('<<ComboboxSelected>>', refresh)
        box.bind('<<ListboxSelect>>', select_skill)
        tk.Button(body, text='学习所选技能', command=learn).pack(pady=4)
        self.ui_actions['learn_Button'] = learn
        self.ui_actions['confirm_Button'] = learn
        refresh()

    def _cards_body(self, body, info):
        activity = Activities(self.state)
        hand = tk.Frame(body)
        hand.pack(fill='x', pady=4)
        history = tk.StringVar()
        tk.Label(body, textvariable=history, justify='left').pack(anchor='w')
        def refresh():
            for widget in hand.winfo_children():
                widget.destroy()
            match = self.state.activities.get('cards')
            # Remove the editor's sample scores/round from the original layout.
            # The active match controls below supply the live card choices.
            visible = {'our_Panel/open_ProjectNode': False,
                       'other_Panel/open_ProjectNode': False, 'open_Button': False,
                       'playTip_Text': False}
            for side, number in (('our_Panel', 0), ('other_Panel', 1)):
                for cup in range(1, 4):
                    visible[f'{side}/cup_Panel/cup_{cup}_Sprite'] = bool(match and match['score'][number] >= cup)
            layer = self.cocos_ui.render('CardLegendUI', (800, 480),
                                        text={'times_BitmapFontLabel': str(match['round'] if match else 1)},
                                        visible=visible)
            if hasattr(self, 'ui_art_label') and self.ui_art_label.winfo_exists():
                photo = ImageTk.PhotoImage(layer)
                self.ui_art_label.configure(image=photo)
                self.ui_art_label.image = photo
            if not match:
                info.set(f'每局消耗 1 张卡牌券，五回合比星级。卡牌券：{self.state.count("220008")}')
                return
            score = f'{match["score"][0]} : {match["score"][1]}'
            if match['result'] is None:
                enemy = match['enemy'][match['enemy_index']]
                info.set(f'第 {match["round"]}/5 回合 · 比分 {score} · 对手出牌：{enemy["star"]} 星')
                for index, card in enumerate(match['player']):
                    name = self.data.tables['Pet'][card['species']]['name']
                    tk.Button(hand, text=f'{name}\n{card["star"]} 星',
                              state='disabled' if index in match['used'] else 'normal',
                              command=lambda i=index: action(lambda: activity.play_card(i))).pack(side='left', padx=3)
            else:
                info.set(f'{ {1: "胜利", 0: "平局", -1: "失败"}[match["result"]]} · 比分 {score}')
                if match['result'] == 1:
                    reward = match['reward']
                    row = (self.data.tables['Pet'].get(reward['item']) or self.data.tables['Item'].get(reward['item'])
                           or self.data.tables['Money'].get(reward['item'], {}))
                    info.set(info.get()+f' · {row.get("name", reward["item"])} × {reward["count"]}'
                             + ('（已领取）' if match['claimed'] else '（待领取）'))
                    tk.Button(hand, text='领取奖励', state='disabled' if match['claimed'] else 'normal',
                              command=lambda: action(activity.claim_cards)).pack()
            history.set('\n'.join(f'回合 {i}: 我方 {r["stars"][0]} 星，对手 {r["stars"][1]} 星'
                                  for i, r in enumerate(match['history'], 1)))
        def action(callback):
            try:
                callback()
                refresh()
            except (ValueError, KeyError) as error:
                info.set(str(error))
        tk.Button(body, text='开始新牌局（卡牌券 ×1）', command=lambda: action(activity.start_cards)).pack(pady=4)
        self.ui_actions['open_Button'] = lambda: action(activity.start_cards)
        refresh()

    def _breakthrough_body(self, body, info):
        pets = list(self.state.pets+self.state.bank)
        box = tk.Listbox(body, width=60, height=6)
        box.pack(fill='x')
        for pet in pets:
            row = self.data.tables['PetTuPo'].get(str(pet.breakthrough+1))
            cost = f'{row["costMoneyCount"]} 金币 + {row["stuffCount"]} 突破材料' if row else '已满阶'
            box.insert('end', f'{self.data.tables["Pet"][pet.species]["name"]} +{pet.breakthrough} → {cost}')
        def apply():
            if not box.curselection():
                return
            pet = pets[box.curselection()[0]]
            try:
                self.state.breakthrough_pet(pet.uid)
                info.set(f'突破成功：{self.data.tables["Pet"][pet.species]["name"]} +{pet.breakthrough}')
            except (ValueError, KeyError) as error:
                info.set(str(error))
        tk.Button(body, text='突破所选宠物', command=apply).pack(pady=4)
        self.ui_actions['tuPo_Button'] = apply

    def _fuse_body(self, body, info):
        pets = list(self.state.bank)
        if not pets:
            info.set('银行中没有可合体的宠物；出战宠物不能合体。')
            message = lambda: info.set('先到银行放入两只可合体的宠物。')
            for key in ('add_1_Button', 'add_2_Button', 'heTi_Button'):
                self.ui_actions[key] = message
            return
        frames = tk.Frame(body)
        frames.pack(fill='x')
        boxes = []
        for title in ('左侧宠物', '右侧宠物'):
            frame = tk.Frame(frames)
            frame.pack(side='left', fill='both', expand=True, padx=5)
            tk.Label(frame, text=title).pack()
            box = tk.Listbox(frame, width=28, height=6, exportselection=False)
            box.pack(fill='both')
            boxes.append(box)
        chosen = {'a': None, 'b': None}
        def refresh():
            names = [f'{self.data.tables["Pet"][p.species]["name"]} Lv.{p.level} +{p.breakthrough}'
                     for p in pets]
            for box in boxes:
                selected = box.curselection()
                box.delete(0, 'end')
                for text in names:
                    box.insert('end', text)
                if selected:
                    box.selection_set(selected[0])
            if not boxes[0].curselection() and pets:
                boxes[0].selection_set(0)
            if len(pets) > 1 and not boxes[1].curselection():
                boxes[1].selection_set(1)
            preview()
        def preview(event=None):
            a = pets[boxes[0].curselection()[0]] if boxes[0].curselection() else None
            b = pets[boxes[1].curselection()[0]] if boxes[1].curselection() else None
            chosen['a'], chosen['b'] = a, b
            if not a or not b:
                info.set('选择两只银行宠物。')
                return
            recipe = None
            for row in self.data.tables['PetHeTi'].values():
                if str(row['petAId']) == a.species and str(row['petBId']) == b.species:
                    recipe = row
                    break
            if not recipe:
                info.set('这两只宠物没有原版合体配方。')
                return
            result = self.data.tables['Pet'][str(recipe['petIds'].split(',')[0])]['name']
            costs = '、'.join(f'{self.data.tables["Item"].get(i, self.data.tables["Money"].get(i, {})).get("name", i)}×{n}'
                              for i, n in zip(recipe['costItemIds'].split(','), recipe['costItemCounts'].split(',')))
            info.set(f'结果：{result} Lv.1 · 材料 {costs}')
        def choose(side):
            if not boxes[side].curselection():
                return
            chosen[side] = pets[boxes[side].curselection()[0]]
            preview()
        def fuse():
            if not chosen['a'] or not chosen['b']:
                info.set('请先选择左右两只银行宠物。')
                return
            try:
                pet = self.state.fuse_pets(chosen['a'].uid, chosen['b'].uid)
                pets[:] = list(self.state.bank)
                for box in boxes:
                    box.selection_clear(0, 'end')
                refresh()
                info.set(f'合体成功：{self.data.tables["Pet"][pet.species]["name"]} Lv.{pet.level}')
            except (ValueError, KeyError) as error:
                info.set(str(error))
        for box in boxes:
            box.bind('<<ListboxSelect>>', preview)
        controls = tk.Frame(body)
        controls.pack(pady=4)
        tk.Button(controls, text='选择左侧', command=lambda: choose(0)).pack(side='left', padx=3)
        tk.Button(controls, text='选择右侧', command=lambda: choose(1)).pack(side='left', padx=3)
        tk.Button(controls, text='合体', command=fuse).pack(side='left', padx=3)
        self.ui_actions['add_1_Button'] = lambda: choose(0)
        self.ui_actions['add_2_Button'] = lambda: choose(1)
        self.ui_actions['heTi_Button'] = fuse
        refresh()

    def _merge_body(self, body, info):
        pets = list(self.state.bank)
        if not pets:
            info.set('银行中没有可融合的宠物；参战宠物不能融合。')
            message = lambda: info.set('先到银行放入可融合的宠物。')
            for key in ('add_Button', 'autoAdd_Button', 'merge_Button'):
                self.ui_actions[key] = message
            for index in range(6):
                full = (f'Layer/root_Panel/mergePetNodes_Panel/mergedPetNode_{index+1}'
                        f'/Layer/root_Panel/add_Button')
                self.ui_actions[full] = message
            return
        frame = tk.Frame(body)
        frame.pack(fill='both', expand=True)
        tk.Label(frame, text='银行宠物（选择基础宠物 / 材料）').pack()
        box = tk.Listbox(frame, width=44, height=7, exportselection=False)
        box.pack(fill='x')
        slots = [None]*6
        state = {'base': None}
        slot_text = tk.StringVar()
        def refresh():
            names = [f'{self.data.tables["Pet"][p.species]["name"]} Lv.{p.level} 品质{p.quality}'
                     for p in pets]
            selected = box.curselection()
            box.delete(0, 'end')
            for text in names:
                box.insert('end', text)
            if selected:
                box.selection_set(selected[0])
            elif pets:
                box.selection_set(0)
            slot_text.set('材料：' + '、'.join(
                f'{i+1}.{self.data.tables["Pet"][p.species]["name"]}' if p else f'{i+1}.空'
                for i, p in enumerate(slots)))
            preview()
        def preview():
            base = state['base']
            if not base:
                info.set('先选择基础宠物。')
                return
            recipe = next((r for r in self.data.tables['PetMerge'].values()
                           if int(r['petQuality']) == int(base.quality)), None)
            if not recipe:
                info.set('当前品质没有原版融合配方。')
                return
            info.set(f'基础：{self.data.tables["Pet"][base.species]["name"]} 品质{base.quality} · '
                     f'需要 {recipe["petCount"]} 只 Lv.{recipe["petLevel"]}+ 同品质材料 · '
                     f'货币 {recipe["moneyCount"]}')
        def choose_base():
            if not box.curselection():
                return
            state['base'] = pets[box.curselection()[0]]
            refresh()
        def choose_slot(index):
            if not box.curselection():
                return
            pet = pets[box.curselection()[0]]
            if pet is state['base'] or pet in slots:
                info.set('材料不能是基础宠物或已选材料。')
                return
            slots[index] = pet
            refresh()
        def auto_add():
            base = state['base']
            if not base:
                info.set('先选择基础宠物。')
                return
            recipe = next((r for r in self.data.tables['PetMerge'].values()
                           if int(r['petQuality']) == int(base.quality)), None)
            if not recipe:
                info.set('当前品质没有原版融合配方。')
                return
            slots[:] = [None]*6
            chosen = [p for p in pets if p is not base and int(p.quality) == int(base.quality)
                      and p.level >= int(recipe['petLevel'])]
            for i, pet in enumerate(chosen[:int(recipe['petCount'])]):
                slots[i] = pet
            refresh()
        def merge():
            base = state['base']
            if not base:
                info.set('先选择基础宠物。')
                return
            chosen = [p for p in slots if p]
            try:
                result = self.state.merge_pets(base.uid, [p.uid for p in chosen])
                pets[:] = list(self.state.bank)
                slots[:] = [None]*6
                state['base'] = None
                refresh()
                info.set(f'融合成功：{self.data.tables["Pet"][result.species]["name"]} '
                         f'品质{result.quality}，全属性成长 +0.5。')
            except (ValueError, KeyError) as error:
                info.set(str(error))
        tk.Label(body, textvariable=slot_text, justify='left').pack(pady=4)
        controls = tk.Frame(body)
        controls.pack(pady=4)
        tk.Button(controls, text='设为基础', command=choose_base).pack(side='left', padx=3)
        tk.Button(controls, text='自动填充材料', command=auto_add).pack(side='left', padx=3)
        tk.Button(controls, text='融合', command=merge).pack(side='left', padx=3)
        self.ui_actions['add_Button'] = choose_base
        self.ui_actions['autoAdd_Button'] = auto_add
        self.ui_actions['merge_Button'] = merge
        for index in range(6):
            full = (f'Layer/root_Panel/mergePetNodes_Panel/mergedPetNode_{index+1}'
                    f'/Layer/root_Panel/add_Button')
            self.ui_actions[full] = lambda index=index: choose_slot(index)
        refresh()

    def _area_map_body(self, body, info):
        info.set(f'当前地图：{self.map.info["name"]}（{self.map_id}）\n'
                 '世界地图列出原版 WorldMap 区域；飞行只前往已经到过的城镇。')
        def world_map():
            win = tk.Toplevel(self.root)
            win.title('原版世界地图')
            box = tk.Text(win, width=58, height=22, wrap='word')
            box.pack(fill='both', expand=True)
            for key, row in sorted(self.data.tables['WorldMap'].items(), key=lambda item: int(item[0])):
                names = [self.data.tables['VillageMap'].get(mid, {}).get('name', mid)
                         for mid in str(row['mapIds']).split(',')]
                box.insert('end', f'{row["name"]}（{key}）\n  ' + '、'.join(names) + '\n\n')
            box.config(state='disabled')
        def fly():
            maps = [mid for mid in self.state.visited_maps
                    if str(mid) in self.data.tables['VillageMap']
                    and str(self.data.tables['VillageMap'][str(mid)].get('mapType')) == '2']
            if self.map_id not in maps and str(self.map_id) in self.data.tables['VillageMap']:
                maps.append(self.map_id)
            if not maps:
                info.set('还没有到过可飞行的城镇。')
                return
            win = tk.Toplevel(self.root)
            win.title('选择飞行目的地')
            box = tk.Listbox(win, width=40, height=10)
            box.pack(fill='both', expand=True, padx=8, pady=8)
            for mid in maps:
                box.insert('end', f'{mid}  {self.data.tables["VillageMap"][str(mid)]["name"]}')
            def go():
                if not box.curselection():
                    return
                mid = maps[box.curselection()[0]]
                win.destroy()
                self.close_ui()
                self.load_map(str(mid))
                self.x, self.y = self.map.width*32, self.map.height*32
                if self.map.blocked(self.x, self.y):
                    for radius in range(1, 20):
                        spots = [(tx*64+32, ty*64+32)
                                 for tx in range(max(0, int(self.x//64)-radius),
                                                 min(self.map.width, int(self.x//64)+radius+1))
                                 for ty in range(max(0, int(self.y//64)-radius),
                                                 min(self.map.height, int(self.y//64)+radius+1))
                                 if not self.map.blocked(tx*64+32, ty*64+32)]
                        if spots:
                            self.x, self.y = spots[0]
                            break
                self.event_issue = f'已飞行到 {self.map.info["name"]}。'
            tk.Button(win, text='飞行', command=go).pack(pady=4)
        tk.Button(body, text='世界地图', command=world_map).pack(pady=3)
        tk.Button(body, text='飞行到已到过的城镇', command=fly).pack(pady=3)
        self.ui_actions['worldMap_Button'] = world_map
        self.ui_actions['fly_Button'] = fly

    def _illustrated_body(self, body, info):
        species = list(dict.fromkeys(self.state.encyclopedia or list(self.data.tables['Pet'])[:1]))
        box = tk.Listbox(body, width=36, height=8)
        box.pack(fill='x')
        for key in species:
            row = self.data.tables['Pet'].get(str(key), {})
            box.insert('end', f'{key}  {row.get("name", "")}')
        if species:
            box.selection_set(0)
        def check():
            if not box.curselection():
                info.set('先选择一只已记录的宠物。')
                return
            key = species[box.curselection()[0]]
            row = self.data.tables['Pet'][key]
            skills = '、'.join(self.data.tables['Skill'].get(s, {}).get('name', s)
                              for s in str(row.get('skillIds', '')).split(',') if s and s != '0')
            info.set(f'{row["name"]}（{key}）\n属性：{row.get("kind")} · 品质上限：{row.get("quality")}\n'
                     f'技能：{skills or "无"}')
        check()
        self.ui_actions['check_Button'] = check
        tk.Button(body, text='查看图鉴', command=check).pack(pady=4)

    def _arena_body(self, body, info, arena_id=None, phase=1):
        progress = ArenaProgress(self.state)
        arena = self.data.tables['Arena'].get(str(arena_id)) if arena_id else None
        if not arena:
            arena = next(iter(self.data.tables['Arena'].values()), None)
        if not arena:
            info.set('原版 Arena 表为空。')
            return
        aid = str(arena['keyId'])
        rank = progress.rank(aid)
        title = progress.title_name(aid)
        streak = progress.streak(aid)
        cost = progress.entry_cost(aid)
        npc = progress.next_npc(aid)
        opponent = '无'
        if npc:
            title_row = self.data.tables['ArenaTitle'].get(str(npc.get('titleId', '0')))
            opponent = (f'{title_row["name"] if title_row else "竞技场对手"} · '
                        f'Lv.{npc["petLevel"]} · 排名 {npc["rankInterval"]}')
        money_name = ''
        if cost:
            money_name = (self.data.tables['Money'].get(cost[0]) or
                          self.data.tables['Item'].get(cost[0]) or {}).get('name', cost[0])
        info.set(f'{arena["name"]}\n当前排名：{rank} · 称号：{title} · 连胜：{streak}\n'
                 f'下一位对手：{opponent}\n'
                 f'{"本场免费（连胜中）" if not cost else f"本场消耗 {money_name}×{cost[1]}"}')
        def challenge():
            ok, reason = progress.can_enter(aid)
            if not ok:
                info.set(reason)
                return
            if not any(p.hp > 0 for p in self.state.pets):
                info.set('没有可出战的宠物，不能进入竞技场。')
                return
            # The original closeui yes branch leads to fight type=3.  The host
            # charges the badge when that fight actually starts.
            self.close_ui('yes')
        def leave():
            progress.leave(aid)
            self.close_ui('no')
        def rule():
            win = tk.Toplevel(self.root)
            win.title('竞技场规则')
            text = tk.Text(win, width=62, height=18, wrap='word')
            text.pack(fill='both', expand=True)
            text.insert('1.0', arena.get('rule', ''))
            text.config(state='disabled')
        def share():
            text = f'我在《口袋妖怪单机版》竞技场排名 {rank}，称号 {title}，来挑战我！'
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            info.set('邀请文本已复制到剪贴板。')
        self.ui_actions['challenge_Button'] = challenge
        self.ui_actions['ruleInfo_Button'] = rule
        self.ui_actions['leave_Button'] = leave
        self.ui_actions['close_Button'] = leave
        self.ui_actions['weixin_Button'] = share
        tk.Button(body, text='开始挑战', command=challenge).pack(pady=3)
        tk.Button(body, text='查看规则', command=rule).pack(pady=3)
        tk.Button(body, text='离开竞技场', command=leave).pack(pady=3)

    def _trial_body(self, body, info):
        rows = list(self.data.tables['TrialPet'].values())
        if not rows:
            info.set('原版 TrialPet 表为空。')
            return
        box = tk.Listbox(body, width=38, height=7)
        box.pack(fill='x')
        for row in rows:
            pet = self.data.tables['Pet'].get(str(row['petId']), {})
            box.insert('end', f'{pet.get("name", row["petId"])} Lv.{row["level"]} 次数{row["trialCount"]}')
        box.selection_set(0)
        def trial():
            if not box.curselection():
                return
            row = rows[box.curselection()[0]]
            pet = self.data.tables['Pet'][str(row['petId'])]['name']
            info.set(f'试炼宠物：{pet} Lv.{row["level"]}；技能/天赋按 TrialPet 原表登记。')
        self.ui_actions['trial_Button'] = trial
        self.ui_actions['buy_Button'] = lambda: info.set('试炼宠物购买入口已读取；商店扣费尚未接入。')
        tk.Button(body, text='查看试炼宠物', command=trial).pack(pady=4)

    def _running_body(self, body, info):
        rows = list(self.data.tables['RunningPet'].values())
        box = tk.Listbox(body, width=36, height=7)
        box.pack(fill='x')
        for row in rows:
            box.insert('end', f'{row["name"]}：{row["des"]}')
        if rows:
            box.selection_set(0)
        def join():
            if not box.curselection():
                return
            row = rows[box.curselection()[0]]
            info.set(f'赛宠报名：{row["name"]}；原版赛跑小游戏尚未接入。')
        self.ui_actions['join_Button'] = join
        tk.Button(body, text='报名', command=join).pack(pady=4)

    def _rank_body(self, body, info):
        pages = {
            'fightTag_Button': ('战斗排名', 'FightRank'),
            'integralTag_Button': ('积分排名', 'PetCollectCountRank'),
            'receiveTag_Button': ('领取奖励', 'RankReward'),
            'taoFaTag_Button': ('讨伐', 'RankNpcPet'),
        }
        def show(label, table):
            rows = self.data.tables.get(table, {})
            info.set(f'{label}：原版 {table} 共 {len(rows)} 行。')
        for key, (label, table) in pages.items():
            self.ui_actions[key] = lambda label=label, table=table: show(label, table)
        self.ui_actions['fight_Button'] = lambda: show('挑战排名', 'RankNpcPet')
        self.ui_actions['taoFa_Button'] = lambda: show('讨伐目标', 'RankNpcPet')
        self.ui_actions['monsterInfo_Button'] = lambda: show('怪物资料', 'Pet')
        tk.Button(body, text='战斗排名', command=lambda: show(*pages['fightTag_Button'])).pack(pady=2)
        tk.Button(body, text='怪物资料', command=lambda: show('怪物资料', 'Pet')).pack(pady=2)

    def _treasure_buy_body(self, body, info, par1=None):
        rows = self.data.tables.get('Treasure', {})
        row = rows.get(str(par1)) or next(iter(rows.values()), None)
        if not row:
            info.set('原版 Treasure 表为空。')
            return
        clue = TreasureHunt(self.state).clue(row)
        money = self.data.tables.get('Money', {}).get(clue['money'], {})
        info.set(f'{clue["text"]}\n需花费 {clue["price"]} {money.get("name", clue["money"])}；'
                 '购买后获得原版行配置的放大镜。')
        def buy():
            try:
                entry = TreasureHunt(self.state).buy(row['keyId'])
            except (ValueError, KeyError) as error:
                info.set(str(error))
                return
            self.close_ui('yes')
        self.ui_actions['buy_Button'] = buy
        self.ui_actions['close_Button'] = lambda: self.close_ui('no')
        tk.Button(body, text='购买藏宝图', command=buy).pack(pady=3)

    def _treasure_tip_body(self, body, info):
        hunt = TreasureHunt(self.state)
        row = None
        entry = hunt.active()
        if entry:
            row = self.data.tables['Treasure'][str(entry['id'])]
        else:
            row = next(iter(self.data.tables.get('Treasure', {}).values()), None)
        if not row:
            info.set('原版 Treasure 表为空。')
            return
        clue = hunt.clue(row)
        info.set(f'{clue["text"]}\n线索地图：{clue["map"]}')
        self.ui_actions['confirm_Button'] = lambda: self.close_ui('yes')
        tk.Button(body, text='确认', command=lambda: self.close_ui('yes')).pack(pady=3)

    def _treasure_body(self, body, info, par1=None):
        rows = list(self.data.tables.get('Treasure', {}).values())
        hunt = TreasureHunt(self.state)
        entry = hunt.active()
        row = None
        if entry:
            row = self.data.tables['Treasure'][str(entry['id'])]
        if row is None:
            if par1 and str(par1) in self.data.tables.get('Treasure', {}):
                row = self.data.tables['Treasure'][str(par1)]
            if row is None:
                map_name = str(getattr(getattr(self, 'map', None), 'info', {}).get('name', ''))
                row = next((r for r in rows if str(r.get('name')) == map_name), None)
            if row is None:
                row = rows[0] if rows else None
        if not row:
            info.set('原版 Treasure 表为空。')
            return
        magnifier = self.state.count('220007')
        clue = hunt.clue(row)
        text = (f'{clue["text"]}\n'
                f'线索地图：{clue["map"]} · 宝箱类型：{"、".join(clue["chests"]) or "未知"}\n'
                f'当前放大镜：{magnifier} 个 · 每次使用消耗 1 个')
        if entry:
            pos = self.data.tables.get('TChestPos', {}).get(str(entry['pos_id']), {})
            status = '已显现，请前往地图寻找' if entry.get('revealed') else '尚未显现'
            text += (f'\n当前宝藏：{pos.get("pos", "?")} 格 · {status}')
        else:
            text += '\n当前没有正在寻找的藏宝图，请先在藏宝图购买页取得一张。'
        info.set(text)

        def search():
            current = hunt.active()
            if not current:
                info.set('当前没有正在寻找的藏宝图；请先购买藏宝图。')
                return
            try:
                hunt.use_magnifier(current['pos_id'])
            except (ValueError, KeyError) as error:
                info.set(str(error))
                return
            # The original use button sends the find event and closes the clue
            # panel; the host then walks the map and opens the revealed chest.
            self.close_ui('yes')

        def give_up():
            try:
                hunt.give_up()
            except ValueError as error:
                info.set(str(error))
                return
            self.close_ui('no')

        self.ui_actions['use_Button'] = search
        self.ui_actions['giveUp_Button'] = give_up
        self.ui_actions['close_Button'] = lambda: self.close_ui('no')
        label = '使用放大镜' if entry else '需要藏宝图'
        tk.Button(body, text=label, command=search).pack(pady=3)
        tk.Button(body, text='放弃', command=give_up).pack(pady=3)

    def _infinite_body(self, body, info, uiid, arena_id=None):
        progress = InfiniteArenaProgress(self.state)
        arena = self.data.tables['InfiniteArena'].get(str(arena_id or 1))
        if not arena:
            arena = next(iter(self.data.tables['InfiniteArena'].values()), None)
        if not arena:
            info.set('原版 InfiniteArena 表为空。')
            return
        aid = str(arena['keyId'])
        level = progress.level(aid)
        row = progress.level_row(aid, level)
        honor = progress.honor()
        money, amount = progress.entry_cost(aid)
        currency = (self.data.tables['Money'].get(money) or {}).get('name', money)
        info.set(f'{arena["name"]}\n{arena["rule"]}\n'
                 f'当前层数：{level} / {progress.max_level()} · 最高：{progress.highest()}\n'
                 f'荣誉：{honor} · 守护者等级：Lv.{row["petLevel"]} · 挑战消耗 {currency}×{amount}')
        if uiid == 21:
            info.set(f'确定要离开无限竞技场吗？\n当前层数：{level} · 荣誉：{honor}')
        def confirm():
            if uiid == 20:
                ok, reason = progress.can_enter(aid)
                if not ok:
                    info.set(reason)
                    return
                if not any(p.hp > 0 for p in self.state.pets):
                    info.set('没有可出战的宠物，不能挑战守护者。')
                    return
            self.close_ui('yes')
        def cancel():
            self.close_ui('no')
        def rule():
            win = tk.Toplevel(self.root)
            win.title('无限竞技场规则')
            text = tk.Text(win, width=62, height=18, wrap='word')
            text.pack(fill='both', expand=True)
            text.insert('1.0', arena.get('rule', ''))
            text.config(state='disabled')
        self.ui_actions['confirm_Button'] = confirm
        self.ui_actions['cancel_Button'] = cancel
        self.ui_actions['close_Button'] = cancel
        self.ui_actions['ruleInfo_Button'] = rule
        tk.Button(body, text='确认', command=confirm).pack(pady=3)
        tk.Button(body, text='取消/离开', command=cancel).pack(pady=3)
        tk.Button(body, text='查看规则', command=rule).pack(pady=3)

    def starter_window(self, key):
        win = tk.Toplevel(self.root)
        win.title('选择初始伙伴')
        win.protocol('WM_DELETE_WINDOW', self.close_ui)
        self.ui_window, self.ui_open = win, True
        row = self.data.tables['InitPet'][str(key)]
        name = self.data.tables['Pet'][str(row['petId'])]['name']
        tk.Label(win, text=f'要选择 {name} 作为伙伴吗？', font=('Microsoft YaHei UI', 14)).pack(padx=24, pady=12)
        art = self.data.pet_image(row['petId'])
        if art is not None:
            art = art.copy()
            art.thumbnail((320, 260))
            photo = ImageTk.PhotoImage(art)
            label = tk.Label(win, image=photo)
            label.image = photo
            label.pack()
        tk.Button(win, text=f'选择 {name}', command=lambda: self.choose_starter(key)).pack(pady=8)
        tk.Button(win, text='再考虑一下', command=self.close_ui).pack(pady=8)

    def _pet_shop_body(self, body, info, key):
        row = self.data.tables['PetShop'][str(key)]
        name = self.data.tables['Pet'][str(row['petId'])]['name']
        currency = self.data.tables['Money'][str(row['moneyType'])]['name']
        info.set(f'{name} Lv.{row["level"]} · {row["price"]} {currency}')
        def buy():
            try:
                pet = self.state.buy_pet(key)
                info.set(f'已购入 {name} Lv.{pet.level}')
            except (ValueError, KeyError) as error:
                info.set(str(error))
        tk.Button(body, text='购买宠物', command=buy).pack(pady=4)
        self.ui_actions['buy_Button'] = buy

    def _bank_body(self, body, info):
        boxes = []
        for title in ('携带宠物', '银行宠物'):
            frame = tk.Frame(body)
            frame.pack(side='left', padx=8)
            tk.Label(frame, text=title).pack()
            box = tk.Listbox(frame, width=30, height=7, exportselection=False)
            box.pack()
            boxes.append(box)
        def refresh():
            for box, pets in zip(boxes, (self.state.pets, self.state.bank)):
                box.delete(0, 'end')
                for pet in pets:
                    box.insert('end', f'{self.data.tables["Pet"][pet.species]["name"]} Lv.{pet.level}')
            info.set(f'携带 {len(self.state.pets)}/{self.state.pet_capacity()} · 银行 {len(self.state.bank)}/{self.state.pet_capacity(True)}')
        def move(to_bank):
            box, pets = (boxes[0], self.state.pets) if to_bank else (boxes[1], self.state.bank)
            if not box.curselection():
                return
            try:
                self.state.move_pet(pets[box.curselection()[0]].uid, to_bank=to_bank)
                refresh()
            except ValueError as error:
                info.set(str(error))
        tk.Button(body, text='存入 →', command=lambda: move(True)).pack(pady=4)
        tk.Button(body, text='← 取出', command=lambda: move(False)).pack(pady=4)
        self.ui_actions['consign_Button'] = lambda: move(True)
        refresh()

    def _roulette_body(self, body, info):
        activity = Activities(self.state)
        box = tk.Listbox(body, width=65, height=6)
        box.pack(fill='x')
        def refresh(paid=False):
            try:
                board = activity.roulette_board(paid_refresh=paid)
                box.delete(0, 'end')
                for index, reward in enumerate(board, 1):
                    row = (self.data.tables['Pet'].get(reward['item']) or self.data.tables['Item'].get(reward['item'])
                           or self.data.tables['Money'].get(reward['item'], {}))
                    box.insert('end', f'{index}. {row.get("name", reward["item"])} × {reward["count"]}')
                info.set(f'轮盘券 {self.state.count("220009")} · 徽章 {self.state.count("700002")}')
            except (ValueError, KeyError) as error:
                info.set(str(error))
        def spin():
            try:
                index, reward = activity.spin_roulette()
                box.selection_clear(0, 'end')
                box.selection_set(index)
                box.see(index)
                info.set(f'获得 {box.get(index)} · 剩余轮盘券 {self.state.count("220009")}')
            except (ValueError, KeyError) as error:
                info.set(str(error))
        tk.Button(body, text='开始（1 张轮盘券）', command=spin).pack(side='left', pady=4)
        tk.Button(body, text='刷新（1 枚徽章）', command=lambda: refresh(True)).pack(side='left', padx=8)
        self.ui_actions['start_Button'] = spin
        self.ui_actions['refresh_Button'] = lambda: refresh(True)
        refresh()

    def lottery_ui(self):
        if self.battle or self.runtime.running or self.ui_open:
            self.event_issue = '请先结束当前对话、界面或战斗。'
            return
        if self.state.functions.get('8', 0) != 1:
            self.event_issue = '抽宠功能尚未在剧情中开启。'
            return
        win = tk.Toplevel(self.root)
        win.title('抽宠')
        win.protocol('WM_DELETE_WINDOW', self.close_ui)
        self.ui_window, self.ui_open = win, True
        layer = self.cocos_ui.render('LuckyDrawUI', (800, 480))
        photo = ImageTk.PhotoImage(layer)
        label = tk.Label(win, image=photo)
        label.image = photo
        label.pack()
        info = tk.StringVar(value='普通抽宠 10 徽章 · 黄金抽宠 25 徽章 · 黄金三连 50 徽章')
        tk.Label(win, textvariable=info).pack()
        def draw(kind, free=False):
            try:
                pets = Activities(self.state).draw_pets(kind, free=free)
                info.set('获得：'+ '、'.join(self.data.tables['Pet'][p.species]['name'] for p in pets)
                         + f' · 剩余徽章 {self.state.count("700002")}')
            except (ValueError, KeyError) as error:
                info.set(str(error))
        buttons = tk.Frame(win)
        buttons.pack(pady=8)
        for title, command in [('免费抽宠', lambda: draw(1, True)), ('普通抽宠', lambda: draw(1)),
                               ('黄金抽宠', lambda: draw(2)), ('黄金三连', lambda: draw(3))]:
            tk.Button(buttons, text=title, command=command).pack(side='left', padx=5)
        tk.Button(buttons, text='关闭', command=self.close_ui).pack(side='left', padx=5)
