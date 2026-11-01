"""Interactive native controls for recovered economy/activity systems."""
import tkinter as tk
from PIL import ImageTk
from activities import Activities


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
