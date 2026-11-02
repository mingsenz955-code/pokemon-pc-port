"""Interactive native controls for recovered economy/activity systems."""
import os
import time
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageTk
from activities import Activities
from achievements import Achievements
from arena import ArenaProgress
from budokan import BudokanProgress
from continuous_login import ContinuousLogin
from daily_tasks import DailyTasks
from game_state import numbers
from infinite_arena import InfiniteArenaProgress
from treasure import TreasureHunt
from running_pet import RunningPetGame


class ActivityUI:
    def _login_body(self, body, info):
        login = ContinuousLogin(self.state)
        body.pack_forget()

        def name_of(kid):
            for table in ('Item', 'Money', 'Pet'):
                row = self.data.tables.get(table, {}).get(str(kid))
                if row:
                    return row['name']
            return str(kid)

        def icon_of(kid):
            row = self.data.tables.get('Item', {}).get(str(kid))
            if row and row.get('texture'):
                return f'ItemIcon/{row["texture"]}'
            return None

        def paint():
            status = login.status()
            rewards = login.rewards()
            layer = self.cocos_ui.render('ContinuousLoginUI', (800, 480), {
                'days_BitmapFontLabel': str(status['day']),
                'info_Text': '连续登录奖励',
                'infoItemName_Text': '',
                'infoItemCount_BitmapFontLabel': '',
            })
            base_hits = dict(self.cocos_ui.hits)
            base_rects = dict(self.cocos_ui.rects)
            base_buttons = dict(self.cocos_ui.buttons)
            base_text = dict(self.cocos_ui.button_text)
            rect = (self.ui_rects.get('goods_ListView')
                    or self.ui_hits.get('goods_ListView') or (223, 171, 739, 412))
            draw = ImageDraw.Draw(layer)
            for index, row in enumerate(rewards[:7]):
                claimable = (index+1 == status['next_day']
                             and not status['claimed_today'] and not status['complete'])
                card = self.cocos_ui.render(
                    'ContinuousLoginItemUI', (70, 90), {
                        'day_BitmapFontLabel': str(index+1),
                        'name_Text': name_of(row['rewardKid'])[:5],
                        'count_BitmapFontLabel': f'x{row["rewardCount"]}',
                    },
                    resources={'icon_Image': icon_of(row['rewardKid']) or ''},
                    visible={'get_Button': claimable})
                x = round(rect[0] + 2 + index * 73)
                y = round(rect[1] + 62)
                layer.alpha_composite(card, (x, y))
                self.ui_hits[f'login_card_{index}'] = (x, y, x+70, y+90)
                self.ui_actions[f'login_card_{index}'] = (
                    lambda value=index: select(value))
                if claimable:
                    self.ui_hits[f'login_claim_{index}'] = (
                        x+9, y+73, x+61, y+90)
                    self.ui_actions[f'login_claim_{index}'] = (
                        lambda: claim())
                if index+1 <= status['day']:
                    draw.rectangle((x+1, y+1, x+68, y+88),
                                   outline='#ffe36e', width=2)
            self.ui_base_layer = layer
            self.ui_hits.update(base_hits)
            self.ui_rects = base_rects
            self.ui_buttons = base_buttons
            self.ui_button_text = base_text
            self.ui_actions['get_Button'] = claim
            self.ui_actions['receive_Button'] = claim
            self.ui_actions['confirm_Button'] = claim
            self.ui_actions['close_Button'] = lambda: self.close_ui('no')
            if hasattr(self, 'ui_art_label') and self.ui_art_label.winfo_exists():
                photo = ImageTk.PhotoImage(layer)
                self.ui_art_label.configure(image=photo)
                self.ui_art_label.image = photo
            if status['complete']:
                info.set('连续登录七天奖励已经全部领取。')
            elif status['claimed_today']:
                info.set('今天已经领取；明天再来领取下一天奖励。')
            elif status['reset']:
                info.set('中断超过一天，连续登录从第一天重新开始。')
            else:
                row = rewards[status['next_day']-1]
                info.set(f'{row["des"]}{name_of(row["rewardKid"])} × {row["rewardCount"]}')

        def select(index):
            rewards = login.rewards()
            if 0 <= index < len(rewards):
                row = rewards[index]
                info.set(f'第 {index+1} 天：{name_of(row["rewardKid"])} ×'
                         f'{row["rewardCount"]}')

        def claim():
            try:
                result = login.claim()
            except (ValueError, KeyError) as error:
                info.set(str(error))
                return
            paint()
            info.set(f'领取成功：{name_of(result["reward"])} × {result["count"]}。'
                     '明天可继续领取。')

        paint()

    def _hatch_body(self, body, info):
            activity = Activities(self.state)
            selected = [0]
            rect = self.ui_hits.get('pets_ListView') or self.ui_rects.get('pets_ListView')
            if not rect:
                rect = (226, 175, 738, 408)
            body.pack_forget()

            def slots():
                return [(index, self.state.activities.get('eggs', {}).get(str(index)))
                        for index in range(10)]

            def available():
                return [key for key in self.data.tables['HatchItem'] if self.state.count(key)]

            def describe(index=None):
                target = selected[0] if index is None else index
                egg = self.state.activities.get('eggs', {}).get(str(target))
                if not egg:
                    info.set('空孵化位。选择下方的放入按钮可以放入宠物蛋。')
                    return
                if egg.get('pet'):
                    info.set(f'{self.data.tables["Pet"][egg["pet"]["species"]]["name"]} 已孵化，待领取。')
                    return
                row = self.data.tables['HatchItem'][egg['item']]
                info.set(f'孵化中 · 经验 {egg["exp"]}/{row["exp"]} · '
                         f'直接孵化需要 {row["moneyCount"]} '
                         f'{self.data.tables["Money"][row["moneyId"]]["name"]}')

            def paint():
                layer = self.cocos_ui.render('HatchRoomUI', (800, 480), {
                    'progress_BitmapFontLabel': f'{sum(1 for _, egg in slots() if egg)}/10',
                    'info_Text': '选择孵化位；战斗获得孵化经验，可用材料孵化或支付金币直接孵化。',
                })
                base_hits = dict(self.cocos_ui.hits)
                base_rects = dict(self.cocos_ui.rects)
                base_buttons = dict(self.cocos_ui.buttons)
                base_text = dict(self.cocos_ui.button_text)
                draw = ImageDraw.Draw(layer)
                font_path = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts/msyh.ttc'
                try:
                    font = ImageFont.truetype(str(font_path), 11)
                except OSError:
                    font = ImageFont.load_default()
                for index, egg in slots():
                    column, line = index % 2, index // 2
                    x = round(rect[0] + 5 + column * 255)
                    y = round(rect[1] + 4 + line * 45)
                    if egg:
                        if egg.get('pet'):
                            name = self.data.tables['Pet'][egg['pet']['species']]['name']
                            text = f'{index+1}. {name} · 待领取'
                        else:
                            row = self.data.tables['HatchItem'][egg['item']]
                            text = (f'{index+1}. {self.data.tables["Item"][egg["item"]]["name"]} '
                                    f'{egg["exp"]}/{row["exp"]}')
                    else:
                        text = f'{index+1}. 空位'
                    draw.rectangle((x, y, x+245, y+38),
                                   fill=(63, 41, 31, 155))
                    draw.text((x+8, y+10), text, font=font,
                              fill=(255, 244, 209))
                    self.ui_hits[f'hatch_slot_{index}'] = (x, y, x+245, y+38)
                    self.ui_actions[f'hatch_slot_{index}'] = (
                        lambda value=index: choose(value))
                    if index == selected[0]:
                        draw.rectangle((x, y, x+245, y+38),
                                       outline='#ffe36e', width=2)
                for index, (label, action) in enumerate((
                        ('放入蛋', put), ('材料孵化', lambda: act('normal')),
                        ('金币孵化', lambda: act('money')), ('取回/领取', lambda: act('take')))):
                    x = round(rect[0] + 8 + index * 126)
                    y = 422
                    draw.rectangle((x, y, x+116, y+32), fill=(143, 76, 44, 220))
                    draw.text((x+22, y+9), label, font=font, fill=(255, 244, 209))
                    self.ui_hits[f'hatch_action_{index}'] = (x, y, x+116, y+32)
                    self.ui_actions[f'hatch_action_{index}'] = action
                self.ui_base_layer = layer
                self.ui_hits.update(base_hits)
                self.ui_rects = base_rects
                self.ui_buttons = base_buttons
                self.ui_button_text = base_text
                self.ui_actions['putIn_Button'] = put
                self.ui_actions['takeBackEgg_Button'] = lambda: act('take')
                self.ui_actions['takeBack_Button'] = lambda: act('take')
                self.ui_actions['hatch_Button'] = lambda: act('normal')
                self.ui_actions['moneyHatch_Button'] = lambda: act('money')
                self.ui_actions['check_Button'] = check
                self.ui_actions['close_Button'] = self.close_ui
                if hasattr(self, 'ui_art_label') and self.ui_art_label.winfo_exists():
                    photo = ImageTk.PhotoImage(layer)
                    self.ui_art_label.configure(image=photo)
                    self.ui_art_label.image = photo

            def choose(index):
                selected[0] = index
                describe()
                paint()

            def put():
                keys = available()
                if not keys:
                    info.set('没有可放入的宠物蛋。')
                    return
                try:
                    activity.put_egg(selected[0], keys[0])
                except (ValueError, KeyError) as error:
                    info.set(str(error))
                    return
                paint()
                info.set('宠物蛋已放入孵化位。')

            def act(kind):
                try:
                    if kind == 'take':
                        activity.take_egg(selected[0])
                    else:
                        activity.hatch(selected[0], use_money=kind == 'money')
                except (ValueError, KeyError) as error:
                    info.set(str(error))
                    return
                paint()
                describe()

            def check():
                self.open_hatch_check(selected[0])

            paint()
            describe()

    def _skill_body(self, body, info):
            from game_state import numbers
            pets = list(self.state.pets)
            if not pets:
                info.set('没有携带的宠物。')
                self.ui_actions['close_Button'] = self.close_ui
                body.pack_forget()
                return
            selected_pet = [0]
            selected_skill = [0]
            choices = []
            pet_rect = self.ui_hits.get('pet_ListView') or self.ui_rects.get('pet_ListView')
            skill_rect = self.ui_hits.get('skill_ListView') or self.ui_rects.get('skill_ListView')
            if not pet_rect:
                pet_rect = (32, 95, 393, 423)
            if not skill_rect:
                skill_rect = (431, 143, 712, 412)
            body.pack_forget()

            def build_choices():
                nonlocal choices
                pet = pets[selected_pet[0]]
                choices = []
                for key in numbers(self.data.tables['Pet'][pet.species]['skillIds']):
                    skill = self.data.tables['Skill'].get(str(key), {})
                    choices.append((str(key), None, skill.get('name', str(key)),
                                    f'{skill.get("moneyCount", 0)} '
                                    f'{self.data.tables["Money"].get(str(skill.get("moneyId")), {}).get("name", "")}',
                                    str(key) in pet.skills))
                for item, row in self.data.tables['SkillItem'].items():
                    key = str(row['skillId'])
                    skill = self.data.tables['Skill'].get(key) or self.data.tables['Talent'].get(key)
                    if self.state.count(item) and skill:
                        choices.append((key, item, skill['name'],
                                        f'卷轴 ×1（持有 {self.state.count(item)}）',
                                        key in pet.skills or key in pet.talents))
                selected_skill[0] = min(selected_skill[0], max(0, len(choices)-1))

            def paint():
                build_choices()
                layer = self.cocos_ui.render('SkillLearnUI', (800, 480), {})
                base_hits = dict(self.cocos_ui.hits)
                base_rects = dict(self.cocos_ui.rects)
                base_buttons = dict(self.cocos_ui.buttons)
                base_text = dict(self.cocos_ui.button_text)
                draw = ImageDraw.Draw(layer)
                try:
                    font = ImageFont.truetype(
                        str(Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts/msyh.ttc'), 11)
                    small = ImageFont.truetype(
                        str(Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts/msyh.ttc'), 9)
                except OSError:
                    font = small = ImageFont.load_default()
                for index, pet in enumerate(pets[:3]):
                    row = self.data.tables['Pet'][pet.species]
                    card = self.cocos_ui.render(
                        'PetListItemUI', (320, 110), {
                            'name_Text': row['name'],
                            'lv_BitmapFontLabel': str(pet.level),
                            'hpHave_BitmapFontLabel': str(pet.hp),
                            'hpMax_BitmapFontLabel': str(pet.stats(self.data.tables)[0]),
                            'enHave_BitmapFontLabel': str(pet.energy),
                            'enMax_BitmapFontLabel': str(pet.stats(self.data.tables)[1]),
                            'friendly_BitmapFontLabel': str(pet.friendly),
                        }, visible={'add_Panel': False})
                    x = round(pet_rect[0] + 20)
                    y = round(pet_rect[1] + index * 110)
                    layer.alpha_composite(card, (x, y))
                    self.ui_hits[f'skill_pet_{index}'] = (x, y, x+320, y+110)
                    self.ui_actions[f'skill_pet_{index}'] = (
                        lambda value=index: choose_pet(value))
                    if index == selected_pet[0]:
                        draw.rectangle((x+1, y+1, x+318, y+108),
                                       outline='#ffe36e', width=2)
                for index, (key, scroll, name, cost, learned) in enumerate(
                        choices[:6]):
                    x = round(skill_rect[0] + 4)
                    y = round(skill_rect[1] + 4 + index * 44)
                    draw.rectangle((x, y, skill_rect[2]-6, y+38),
                                   fill=(63, 41, 31, 160))
                    draw.text((x+8, y+5), name[:8], font=font, fill=(255, 244, 209))
                    draw.text((x+8, y+23), ('已学会 · ' if learned else '') + cost[:16],
                              font=small, fill=(255, 220, 150))
                    button_x = skill_rect[2]-68
                    draw.rectangle((button_x, y+6, skill_rect[2]-10, y+33),
                                   fill=(150, 84, 48, 235))
                    draw.text((button_x+9, y+11), '学习', font=small,
                              fill=(255, 244, 209))
                    self.ui_hits[f'skill_row_{index}'] = (x, y, skill_rect[2]-6, y+38)
                    self.ui_actions[f'skill_row_{index}'] = (
                        lambda value=index: choose_skill(value))
                    self.ui_hits[f'skill_learn_{index}'] = (
                        button_x, y+6, skill_rect[2]-10, y+33)
                    self.ui_actions[f'skill_learn_{index}'] = (
                        lambda value=index: learn_at(value))
                    if index == selected_skill[0]:
                        draw.rectangle((x, y, skill_rect[2]-6, y+38),
                                       outline='#ffe36e', width=2)
                self.ui_base_layer = layer
                self.ui_hits.update(base_hits)
                self.ui_rects = base_rects
                self.ui_buttons = base_buttons
                self.ui_button_text = base_text
                self.ui_actions['learn_Button'] = learn
                self.ui_actions['replace_Button'] = open_replace
                self.ui_actions['confirm_Button'] = learn
                self.ui_actions['close_Button'] = self.close_ui
                if hasattr(self, 'ui_art_label') and self.ui_art_label.winfo_exists():
                    photo = ImageTk.PhotoImage(layer)
                    self.ui_art_label.configure(image=photo)
                    self.ui_art_label.image = photo

            def choose_pet(index):
                if 0 <= index < len(pets):
                    selected_pet[0] = index
                    selected_skill[0] = 0
                    paint()

            def choose_skill(index):
                if 0 <= index < len(choices):
                    selected_skill[0] = index
                    key, scroll, name, cost, learned = choices[index]
                    info.set(f'{name} · {cost}' + (' · 已学会' if learned else ''))
                    paint()

            def learn():
                if not choices:
                    return
                key, scroll, name, cost, learned = choices[selected_skill[0]]
                self.open_skill_learn_confirm(
                    pets[selected_pet[0]].uid, key, scroll=scroll,
                    replace=None, back=6)

            def learn_at(value):
                if 0 <= value < len(choices):
                    selected_skill[0] = value
                    paint()
                    learn()

            def open_replace():
                if not choices:
                    return
                key, scroll, name, cost, learned = choices[selected_skill[0]]
                self.open_skill_replace(pets[selected_pet[0]].uid, key, scroll=scroll)

            paint()

    def _breakthrough_body(self, body, info):
        pets = list(self.state.pets+self.state.bank)
        body.pack_forget()
        box = tk.Listbox(body, width=60, height=6)
        box.pack(fill='x')
        for pet in pets:
            row = self.data.tables['PetTuPo'].get(str(pet.breakthrough+1))
            cost = f'{row["costMoneyCount"]} 金币 + {row["stuffCount"]} 突破材料' if row else '已满阶'
            box.insert('end', f'{self.data.tables["Pet"][pet.species]["name"]} +{pet.breakthrough} → {cost}')
        if pets:
            box.selection_set(0)
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
        body.pack_forget()
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
        self.ui_actions['close_Button'] = self.close_ui
        refresh()

    def _merge_body(self, body, info):
        pets = list(self.state.bank)
        body.pack_forget()
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
        self.ui_actions['close_Button'] = self.close_ui
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
        tables = self.data.tables
        key = str(self.ui_parameters.get('species') or '')
        if key not in tables['Pet']:
            key = str(next(iter(self.state.encyclopedia or list(tables['Pet'])), ''))
        if key not in tables['Pet']:
            info.set('图鉴中没有可显示的宠物。')
            self.ui_actions['close_Button'] = self.close_ui
            body.pack_forget()
            return
        row = tables['Pet'][key]
        skills = '、'.join(tables['Skill'].get(str(s), {}).get('name', str(s))
                          for s in str(row.get('skillIds', '')).split(',')
                          if s and s != '0')
        kind = tables['PetKindEnum'].get(str(row.get('kind')), {}).get('name', row.get('kind'))
        description_lines = [str(row.get("des", ""))[i:i+14]
                            for i in range(0, min(len(str(row.get("des", ""))), 28), 14)]
        skill_lines = [skills[i:i+14] for i in range(0, min(len(skills), 28), 14)] or ['无']
        description = '\n'.join(description_lines + [
            f'种族：{kind}',
            f'星级：{row.get("starLevel")}  最大等级：{row.get("maxLevel")}',
            '技能：' + ' / '.join(skill_lines),
        ])
        layer = self.cocos_ui.render('IllustratedPetInfoUI', (800, 480), {
            'name_Text': row['name'],
            'number_BitmapFontLabel': '',
            'info_Text': description,
            'infoTitle_1_Text': '属性',
            'infoTitle_2_Text': '技能',
        })
        art = self.data.pet_image(key)
        if art is not None:
            art = art.copy()
            art.thumbnail((140, 140), Image.Resampling.LANCZOS)
            layer.alpha_composite(art, (402-art.width//2, 154-art.height//2))
        self.ui_base_layer = layer
        self.ui_hits = dict(self.cocos_ui.hits)
        self.ui_rects = dict(self.cocos_ui.rects)
        self.ui_buttons = dict(self.cocos_ui.buttons)
        self.ui_button_text = dict(self.cocos_ui.button_text)
        self.ui_actions['check_Button'] = self.close_ui
        self.ui_actions['close_Button'] = self.close_ui
        info.set(f'{row["name"]}（{key}）')
        if getattr(self, 'ui_art_label', None) is not None:
            photo = ImageTk.PhotoImage(layer)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
        body.pack_forget()

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
        body.pack_forget()
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
        self.ui_actions['close_Button'] = self.close_ui
        tk.Button(body, text='查看试炼宠物', command=trial).pack(pady=4)

    def _achievement_body(self, body, info):
            """Original AchievementUI rows; only locally verified rows are claimable."""
            from game_state import numbers
            api = Achievements(self.state)
            status_names = {'ready': '可领取', 'progress': '未完成',
                            'claimed': '已领取', 'unsupported': '未接入'}
            rows = []
            selected = [0]
            scroll = [0]
            rect = self.ui_hits.get('item_ScrollView') or self.ui_rects.get('item_ScrollView')
            if not rect:
                rect = (67, 92, 722, 419)
            body.pack_forget()

            def reward_text(row):
                parts = []
                for item_id, count in zip(numbers(row.get('rewardIds')),
                                          numbers(row.get('rewardCounts'))):
                    item = (self.data.tables.get('Item', {}).get(str(item_id))
                            or self.data.tables.get('Pet', {}).get(str(item_id))
                            or self.data.tables.get('Money', {}).get(str(item_id), {}))
                    parts.append(f'{item.get("name", item_id)}×{count}')
                return '、'.join(parts) or '无'

            def paint():
                layer = self.cocos_ui.render('AchievementUI', (800, 480), {
                    'score_BitmapFontLabel': str(api.score()),
                    'tips_Text': '',
                })
                base_hits = dict(self.cocos_ui.hits)
                base_rects = dict(self.cocos_ui.rects)
                base_buttons = dict(self.cocos_ui.buttons)
                base_text = dict(self.cocos_ui.button_text)
                draw = ImageDraw.Draw(layer)
                for index, entry in enumerate(rows[scroll[0]:scroll[0]+4]):
                    current = entry['current']
                    progress = '未接入' if current is None else f'{current}/{entry["target"]}'
                    card = self.cocos_ui.render(
                        'AchievementItemUI', (700, 80), {
                            'name_Text': '',
                            'info_Text': '',
                            'progress_BitmapFontLabel': '',
                            'score_BitmapFontLabel': f'+{entry["score"]}',
                        },
                        visible={'receive_Button': False})
                    card = card.resize((650, 74), Image.Resampling.LANCZOS)
                    x = round(rect[0] + 2)
                    y = round(rect[1] + 4 + index * 78)
                    layer.alpha_composite(card, (x, y))
                    try:
                        font = ImageFont.truetype(
                            str(Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts/msyh.ttc'), 11)
                        small = ImageFont.truetype(
                            str(Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts/msyh.ttc'), 9)
                    except OSError:
                        font = small = ImageFont.load_default()
                    color = ('#8b5a2b' if entry['status'] == 'ready'
                             else '#6f6258' if entry['status'] == 'claimed' else '#4f443b')
                    draw.text((x+190, y+8), entry['name'][:12], font=font, fill=color)
                    draw.text((x+190, y+28), entry['des'][:18], font=small, fill=color)
                    draw.text((x+300, y+48), progress, font=small, fill=color)
                    if entry['status'] == 'ready':
                        draw.text((x+575, y+30), '领取', font=font, fill='#9b4b12')
                    self.ui_hits[f'achievement_card_{index}'] = (x, y, x+650, y+74)
                    if scroll[0] + index == selected[0]:
                        draw.rectangle((x+1, y+1, x+648, y+72),
                                       outline='#ffe36e', width=2)
                    if entry['status'] == 'ready':
                        self.ui_hits[f'achievement_receive_{index}'] = (
                            x+560, y+24, x+650, y+64)
                self.ui_base_layer = layer
                self.ui_hits.update(base_hits)
                self.ui_rects = base_rects
                self.ui_buttons = base_buttons
                self.ui_button_text = base_text
                for index in range(4):
                    self.ui_actions[f'achievement_card_{index}'] = (
                        lambda value=index: select(scroll[0]+value))
                    self.ui_actions[f'achievement_receive_{index}'] = (
                        lambda value=index: claim(scroll[0]+value))
                if hasattr(self, 'ui_art_label') and self.ui_art_label.winfo_exists():
                    photo = ImageTk.PhotoImage(layer)
                    self.ui_art_label.configure(image=photo)
                    self.ui_art_label.image = photo

            def select(index):
                if not 0 <= index < len(rows):
                    return
                selected[0] = index
                entry = rows[index]
                current = entry['current']
                progress = '未接入' if current is None else f'{current}/{entry["target"]}'
                info.set(f'原版成就共 {len(api.rows)} 行 · 已领取 {len(api.claimed())} 行 · '
                         f'积分 {api.score()}\n'
                         f'{entry["name"]} · {status_names[entry["status"]]}\n'
                         f'{entry["des"]}\n'
                         f'进度：{progress} · 积分：{entry["score"]}\n'
                         f'奖励：{reward_text(entry["row"])}')
                paint()

            def claim(index=None):
                if not rows:
                    info.set('当前没有可领取的成就。')
                    return
                target = selected[0] if index is None else index
                if not 0 <= target < len(rows):
                    return
                entry = rows[target]
                try:
                    result = api.claim(entry['id'])
                except (ValueError, KeyError) as error:
                    info.set(str(error))
                    return
                refresh()
                info.set(f'领取成功：{entry["name"]} · 积分 +{result["score"]} · '
                         f'奖励已进入背包/宠物栏。')

            def refresh():
                nonlocal rows
                rows = api.entries(None)
                selected[0] = min(max(0, selected[0]), max(0, len(rows)-1))
                scroll[0] = min(scroll[0], max(0, len(rows)-4))
                info.set(f'原版成就共 {len(api.rows)} 行 · 当前显示 {len(rows)} 行 · '
                         f'已领取 {len(api.claimed())} 行 · 积分 {api.score()}')
                paint()

            def wheel(event):
                step = -1 if event.delta > 0 else 1
                top = max(0, len(rows)-4)
                scroll[0] = min(top, max(0, scroll[0]+step))
                paint()

            self.ui_actions['receive_Button'] = lambda: claim(selected[0])
            self.ui_actions['achievement_receive'] = lambda: claim(selected[0])
            self.ui_actions['close_Button'] = self.close_ui
            if hasattr(self, 'ui_art_label'):
                self.ui_art_label.bind('<MouseWheel>', wheel)
            refresh()

    def _budokan_body(self, body, info, budokan_id=1):
        """TrialTowerUI: twenty ordered gym battles, original event gate."""
        progress = BudokanProgress(self.state)
        try:
            gym = progress.gym(budokan_id)
            rows = progress.opponents(budokan_id)
        except KeyError as error:
            info.set(str(error))
            self.ui_actions['close_Button'] = lambda: self.close_ui('no')
            return
        wins = progress.wins(budokan_id)
        total = progress.total(budokan_id)
        current = progress.next_npc(budokan_id)
        current_text = (f'下一位：{current.get("name", current["keyId"])}'
                        if current else '二十场试练已全部完成')
        info.set(f'{gym["name"]}：{wins} / {total} 场胜利。'
                 f'{current_text}\n'
                 '全部挑战胜利可以获得本道馆的高级进化材料；'
                 '只能按原表顺序挑战下一位试练人。')
        # The original TrialTowerUI serializes only its title; the twenty
        # TrialTowerItemUI rows are created dynamically by the original
        # layer.  Draw those rows inside the original frame rather than
        # appending a second, unrelated Tk list below the art.
        base = getattr(self, 'ui_base_layer', None)
        if base is not None:
            draw = ImageDraw.Draw(base, 'RGBA')
            font_path = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts/msyh.ttc'
            try:
                font = ImageFont.truetype(str(font_path), 13)
                small = ImageFont.truetype(str(font_path), 11)
                head = ImageFont.truetype(str(font_path), 15)
            except OSError:
                font = small = head = ImageFont.load_default()
            draw.rounded_rectangle((88, 88, 780, 442), radius=8,
                                   fill=(25, 30, 28, 235),
                                   outline=(230, 190, 120, 180), width=2)
            draw.text((108, 99), f'{gym["name"]}   {wins} / {total}',
                      font=head, fill='#ffe3a0')
            draw.text((610, 101), current_text, font=small, fill='#d9d0bd')
            for index, npc in enumerate(rows):
                column, row = divmod(index, 10)
                x = 108+column*344
                y = 130+row*30
                if index < wins:
                    color, mark = (142, 200, 130, 255), '✓'
                elif index == wins:
                    color, mark = (255, 220, 110, 255), '▶'
                else:
                    color, mark = (150, 150, 145, 255), '·'
                if index == wins:
                    draw.rounded_rectangle((x-10, y-4, x+326, y+23), radius=5,
                                           fill=(80, 70, 35, 210))
                pets = []
                for key in numbers(npc.get('petIds')):
                    pet = self.data.tables['BudokanNpcPet'].get(str(key), {})
                    species = self.data.tables['Pet'].get(str(pet.get('petId')), {})
                    if species:
                        pets.append(species.get('name', pet.get('petId')))
                text = f'{mark} {index+1:02d}  {npc.get("name", "")}'
                if pets:
                    text += f'  {pets[0]}等{len(pets)}只'
                draw.text((x, y), text, font=font, fill=color)
                draw.text((x+274, y+1), '已通过' if index < wins else (
                    '挑战' if index == wins else '未解锁'), font=small, fill=color)
            photo = ImageTk.PhotoImage(base)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
        def accept():
            if progress.complete(budokan_id):
                info.set('本道馆二十场试练已经全部完成。')
                return
            self.close_ui('yes')
        def leave():
            self.close_ui('no')
        self.ui_actions['confirm_Button'] = accept
        self.ui_actions['challenge_Button'] = accept
        self.ui_actions['yes_Button'] = accept
        self.ui_actions['close_Button'] = leave
        self.ui_actions['no_Button'] = leave
        tk.Button(body, text='开始下一场试练', bg='#5b7c52', fg='white',
                  command=accept).pack(pady=4)

    def _running_open(self, uiid):
        from event_runtime import Request
        self.open_ui(Request('openui', 'running-pet', 1,
                             {'parameters': {'uiid': uiid}}))

    def _running_body(self, body, info):
        """RunningPetWelUI: original medal gate and join button."""
        game = RunningPetGame(self.state)
        medals = self.state.count(game.MEDAL)
        info.set(f'参加宠物赛跑可以获得游戏奖牌，换取精美礼品。\n'
                 f'当前游戏奖牌：{medals}\n报名至少需要 {game.MIN_BET} 枚；'
                 f'押注获胜按每只赛宠的原始倍率结算。')
        def join():
            if not game.can_enter():
                self._running_open(43)
                return
            self.running_session = game.new_session()
            self._running_open(40)
        self.ui_actions['join_Button'] = join
        self.ui_actions['confirm_Button'] = join
        self.ui_actions['close_Button'] = lambda: self.close_ui('no')
        tk.Button(body, text='参加赛跑', command=join).pack(pady=4)

    def _running_medal_body(self, body, info):
        """Original MedalShop row 801: 1 badge -> 100 running-pet medals."""
        row = self.data.tables.get('MedalShop', {}).get('801')
        if not row:
            info.set('原版 MedalShop 缺少 801 奖牌商品。')
            self.ui_actions['close_Button'] = lambda: self.close_ui('no')
            return
        money = self.data.tables['Money'][str(row['moneyType'])]['name']
        goods = self.data.tables['Money'][str(row['goodsKid'])]['name']
        price, count_got = int(row['price']), int(row['gotCount'])
        info.set(f'{row["name"]}：{row.get("des", "")}\n'
                 f'花费 {price} {money}，获得 {count_got} {goods}；'
                 f'当前{money} {self.state.count(row["moneyType"])}。')
        def buy():
            if self.state.count(row['moneyType']) < price:
                info.set(f'{money}不足，无法购买 {count_got} 枚奖牌。')
                return
            with self.state.transaction():
                self.state.consume([row['moneyType']], [price])
                self.state.grant(row['goodsKid'], count_got)
            self.running_session = None
            self.running_result = None
            self._running_open(39)
        self.ui_actions['confirm_Button'] = buy
        self.ui_actions['buy_Button'] = buy
        for key in ('left_Button', 'right_Button'):
            self.ui_actions[key] = lambda: info.set('原版奖牌商品固定购买 1 组（100 枚）。')
        self.ui_actions['close_Button'] = lambda: self.close_ui('no')
        tk.Button(body, text=f'购买 {count_got} 枚奖牌', command=buy).pack(pady=4)

    def _running_ready_body(self, body, info):
        game = RunningPetGame(self.state)
        if not self.running_session or self.running_session.get('settled'):
            try:
                self.running_session = game.new_session()
            except ValueError:
                info.set('游戏奖牌不足 10 枚，无法报名赛跑。')
                for key in ('left_Button', 'right_Button', 'confirm_Button'):
                    self.ui_actions[key] = lambda: info.set('游戏奖牌不足 10 枚，无法报名赛跑。')
                self.ui_actions['close_Button'] = lambda: self.close_ui('no')
                return
        session = self.running_session
        choices = tk.Frame(body)
        choices.pack(fill='x')
        buttons = []
        def update_art():
            label = getattr(self, 'ui_art_label', None)
            if label is None:
                return
            row = session['contenders'][session['selected']]
            layer = self.cocos_ui.render(
                'RunningPetReadyUI', (800, 480),
                {'num_BitmapFontLabel': str(session['selected']+1),
                 'override_BitmapFontLabel': f'{row["override"]:.1f}',
                 'count_BitmapFontLabel': str(session['bet']),
                 'have_BitmapFontLabel': f'x{self.state.count(game.MEDAL)}'})
            self.ui_base_layer = layer.copy()
            self.ui_hits = dict(self.cocos_ui.hits)
            self.ui_buttons = dict(self.cocos_ui.buttons)
            self.ui_button_text = dict(self.cocos_ui.button_text)
            photo = ImageTk.PhotoImage(layer)
            label.config(image=photo)
            label.image = photo
        def refresh():
            for button in buttons:
                button.destroy()
            buttons.clear()
            selected = session['selected']
            for contender in session['contenders']:
                mark = '▶ ' if contender['index'] == selected else ''
                button = tk.Button(
                    choices, text=(f'{mark}{contender["index"]+1}号 '
                                   f'{contender["name"]} · 倍率 {contender["override"]:.1f}'),
                    command=lambda i=contender['index']: choose(i))
                button.pack(side='left', padx=2, pady=2)
                buttons.append(button)
            row = session['contenders'][selected]
            update_art()
            info.set(f'请选择 1–4 号赛宠；当前选择 {selected+1} 号 {row["name"]}。\n'
                     f'原始胜率公式 1/(1.2+倍率/3)，当前约 '
                     f'{game.win_probability(row["override"])*100:.1f}%；'
                     f'押注 {session["bet"]}，上限 {game.max_bet()}。')
        def choose(index):
            game.select(session, index)
            refresh()
        def step(delta):
            game.adjust_bet(session, delta)
            refresh()
        def confirm():
            try:
                game.settle(session)
            except (ValueError, KeyError) as error:
                info.set(str(error))
                return
            self.running_result = session
            self._running_open(41)
        self.ui_actions['left_Button'] = lambda: step(-1)
        self.ui_actions['right_Button'] = lambda: step(1)
        self.ui_actions['confirm_Button'] = confirm
        self.ui_actions['close_Button'] = lambda: self.close_ui('no')
        refresh()
        tk.Button(body, text='押注 -1', command=lambda: step(-1)).pack(side='left', padx=3)
        tk.Button(body, text='押注 +1', command=lambda: step(1)).pack(side='left', padx=3)
        tk.Button(body, text='开始比赛', command=confirm).pack(side='left', padx=8)

    def _running_result_body(self, body, info):
        session = getattr(self, 'running_result', None)
        if not session:
            info.set('当前没有赛跑结果。')
            self.ui_actions['confirm_Button'] = lambda: info.set('当前没有赛跑结果。')
            self.ui_actions['close_Button'] = lambda: self.close_ui('no')
            return
        game = RunningPetGame(self.state)
        info.set(game.result_text(session)
                 + f'\n连胜：{self.state.activities.get("running_pet", {}).get("streak", 0)} 次'
                 + f' · 当前拥有：{self.state.count(game.MEDAL)} 枚。')
        won = bool(session.get('winner') == session.get('selected'))
        stats = self.state.activities.get('running_pet', {})
        label = getattr(self, 'ui_art_label', None)
        if label is not None:
            mapping = {
                'winTimes_BitmapFontLabel': str(stats.get('streak', 0)),
                'get_BitmapFontLabel': f'x{abs(int(session.get("delta", 0)))}',
                'have_BitmapFontLabel': f'x{self.state.count(game.MEDAL)}',
            }
            visible = {
                'winTitle_Text': won, 'winTip_Text': won,
                'winTimesTag_Text': False, 'winTimes_BitmapFontLabel': False,
                'times_Text': False, 'getTag_Text': won, 'get_Sprite': won,
                'get_BitmapFontLabel': won,
                'loseTitle_Text': not won, 'loseTip_Text': not won,
            }
            layer = self.cocos_ui.render('RunningPetResultUI', (800, 480),
                                         mapping, visible)
            self.ui_base_layer = layer.copy()
            self.ui_hits = dict(self.cocos_ui.hits)
            self.ui_buttons = dict(self.cocos_ui.buttons)
            self.ui_button_text = dict(self.cocos_ui.button_text)
            photo = ImageTk.PhotoImage(layer)
            label.config(image=photo)
            label.image = photo
        def again():
            try:
                self.running_session = game.new_session()
            except ValueError as error:
                info.set(str(error))
                return
            self.running_result = None
            self._running_open(40)
        self.ui_actions['confirm_Button'] = again
        self.ui_actions['close_Button'] = lambda: self.close_ui('no')
        tk.Button(body, text='继续参赛', command=again).pack(pady=4)

    def _running_race_body(self, body, info):
        """RunningPetMapUI: four original armatures, 8s winner timeline."""
        session = getattr(self, 'running_result', None)
        if not session or not session.get('times'):
            info.set('没有正在进行的赛跑。')
            self.ui_actions['close_Button'] = lambda: self.close_ui('no')
            for key in ('num_Button', 'numSelected_Button'):
                self.ui_actions[key] = lambda: info.set('没有正在进行的赛跑。')
            return
        label = getattr(self, 'ui_art_label', None)
        if label is None:
            info.set('原版赛跑地图未加载。')
            self.ui_actions['close_Button'] = lambda: self.close_ui('no')
            for key in ('num_Button', 'numSelected_Button'):
                self.ui_actions[key] = lambda: info.set('原版赛跑地图未加载。')
            return
        base = self.ui_base_layer.copy()
        # RunningPetMapUI serialises its four RunnerNode placeholders and a
        # static countdown "3" in the layout. The original scene replaces those
        # at runtime; erase the placeholder art with track texture and draw the
        # live HUD/countdown on top instead of leaving duplicated labels.
        try:
            clean_track = base.crop((500, 145, 660, 300))
            base.paste(clean_track, (325, 145))
        except ValueError:
            pass
        token = object()
        self.running_race_token = token
        started = time.monotonic()
        self.running_race_done = False
        font_path = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts/msyh.ttc'
        try:
            font = ImageFont.truetype(str(font_path), 16)
            small = ImageFont.truetype(str(font_path), 12)
            big = ImageFont.truetype(str(font_path), 64)
        except OSError:
            font = small = big = ImageFont.load_default()
        def draw_race():
            if (getattr(self, 'running_race_token', None) is not token
                    or not self.ui_window or not self.ui_window.winfo_exists()):
                return
            elapsed = time.monotonic()-started
            frame = base.copy()
            draw = ImageDraw.Draw(frame)
            # Left lane HUD covers the serialised placeholder number/odds nodes.
            draw.rectangle((0, 0, 207, 480), fill=(25, 36, 29, 238))
            draw.line((207, 0, 207, 480), fill=(255, 226, 130, 180), width=2)
            # Start countdown occupies the area where the layout stores its
            # static "3" sprite; after three seconds only clean track remains.
            if elapsed < 3.0:
                count = max(1, 3-int(elapsed))
                draw.rounded_rectangle((360, 170, 448, 270), radius=18,
                                       fill=(25, 36, 29, 214),
                                       outline=(255, 226, 130, 220), width=3)
                draw.text((392, 178), str(count), font=big, fill='#ffe36e')
            for index, contender in enumerate(session['contenders']):
                run_time = session['times'][index]
                ratio = min(1.0, elapsed/run_time)
                x0, x1 = 226, 724
                x = x0 + (x1-x0)*ratio
                y = 132 + index*78
                image = self.data.armature(contender['filePath'], 'standdown')
                if image is not None:
                    image = image.copy()
                    image.thumbnail((88, 60), Image.Resampling.LANCZOS)
                    frame.alpha_composite(image, (round(x-image.width/2),
                                                  round(y-image.height)))
                selected = index == session['selected']
                color = '#ffe36e' if selected else '#f2e7cf'
                draw.rounded_rectangle((12, y-52, 198, y-24), radius=5,
                                       fill=(48, 62, 47, 235))
                draw.text((18, y-51), f'{index+1} {contender["name"]}  '
                                      f'×{contender["override"]:.1f}',
                          font=small, fill=color)
                if selected:
                    draw.polygon(((211, y-8), (223, y), (211, y+8)),
                                 fill='#ffe36e')
                draw.line((x0, y, x1, y), fill=(255, 230, 130, 110), width=2)
                draw.ellipse((x-5, y-5, x+5, y+5), fill=color)
                if ratio >= 1.0:
                    draw.text((x1-3, y-50), '冠军', font=small, fill='#ffe36e')
            draw.rounded_rectangle((260, 12, 540, 46), radius=8,
                                   fill=(32, 43, 36, 210))
            draw.text((272, 18), f'赛跑中… {elapsed:4.1f}s / 8.0s',
                      font=font, fill='#fff3d0')
            photo = ImageTk.PhotoImage(frame)
            self.running_race_frame = frame
            label.config(image=photo)
            label.image = photo
            if elapsed >= RunningPetGame.WINNER_RUN_TIME and not self.running_race_done:
                self.running_race_done = True
                self.root.after(350, finish)
                return
            self.root.after(40, draw_race)
        def finish():
            if getattr(self, 'running_race_token', None) is not token:
                return
            self._running_open(42)
        self.ui_actions['close_Button'] = lambda: self.close_ui('no')
        for key in ('num_Button', 'numSelected_Button'):
            self.ui_actions[key] = lambda: info.set('比赛已经开始，不能更改选择。')
        info.set('比赛进行中：冠军将在 8 秒内到达终点。')
        draw_race()

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
        body.pack_forget()
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
        self.ui_actions['close_Button'] = self.close_ui

    def _bank_body(self, body, info):
            state = self.state
            selected = [0]
            scroll = [0]
            rect = self.ui_hits.get('pets_ListView') or self.ui_rects.get('pets_ListView')
            if not rect:
                rect = (226, 175, 738, 408)
            body.pack_forget()

            def entries():
                return ([('party', pet) for pet in state.pets]
                        + [('bank', pet) for pet in state.bank])

            def paint():
                rows = entries()
                layer = self.cocos_ui.render('PetBankUI', (800, 480), {
                    'info_Text': '选择宠物后可存入银行，或从银行取回队伍。',
                    'progress_BitmapFontLabel': f'{len(state.bank)}/{state.pet_capacity(True)}',
                })
                base_hits = dict(self.cocos_ui.hits)
                base_rects = dict(self.cocos_ui.rects)
                base_buttons = dict(self.cocos_ui.buttons)
                base_text = dict(self.cocos_ui.button_text)
                draw = ImageDraw.Draw(layer)
                start = scroll[0]
                for index, (where, pet) in enumerate(rows[start:start+8]):
                    row = self.data.tables['Pet'][pet.species]
                    card = self.cocos_ui.render(
                        'PetBankItemUI', (120, 90), {
                            'name_Text': row['name'][:5],
                            'lv_BitmapFontLabel': str(pet.level),
                        },
                        visible={'getBack_Button': where == 'bank'})
                    art = self.data.pet_image(pet.species)
                    if art is not None:
                        art = art.copy()
                        art.thumbnail((54, 54), Image.Resampling.LANCZOS)
                        card.alpha_composite(art, (60-art.width//2, 42-art.height//2))
                    column, line = index % 4, index // 4
                    x = round(rect[0] + 4 + column * 126)
                    y = round(rect[1] + 4 + line * 96)
                    layer.alpha_composite(card, (x, y))
                    self.ui_hits[f'bank_card_{index}'] = (x, y, x+120, y+90)
                    self.ui_actions[f'bank_card_{index}'] = (
                        lambda value=index: select(start+value))
                    if where == 'bank':
                        self.ui_hits[f'bank_back_{index}'] = (
                            x+25, y+73, x+95, y+90)
                        self.ui_actions[f'bank_back_{index}'] = (
                            lambda value=index: withdraw(start+value))
                    if start + index == selected[0]:
                        draw.rectangle((x+1, y+1, x+118, y+88),
                                       outline='#ffe36e', width=2)
                self.ui_base_layer = layer
                self.ui_hits.update(base_hits)
                self.ui_rects = base_rects
                self.ui_buttons = base_buttons
                self.ui_button_text = base_text
                self.ui_actions['consign_Button'] = deposit
                self.ui_actions['close_Button'] = self.close_ui
                if hasattr(self, 'ui_art_label') and self.ui_art_label.winfo_exists():
                    photo = ImageTk.PhotoImage(layer)
                    self.ui_art_label.configure(image=photo)
                    self.ui_art_label.image = photo

            def select(index):
                rows = entries()
                if not 0 <= index < len(rows):
                    return
                selected[0] = index
                where, pet = rows[index]
                row = self.data.tables['Pet'][pet.species]
                info.set(f'{row["name"]} Lv.{pet.level} · '
                         f'{"队伍中" if where == "party" else "银行中"}')
                paint()

            def deposit():
                rows = entries()
                if not rows:
                    return
                selected[0] = min(selected[0], len(rows)-1)
                where, pet = rows[selected[0]]
                if where != 'party':
                    info.set('请选择队伍中的宠物再存入银行。')
                    return
                try:
                    state.move_pet(pet.uid, to_bank=True)
                except ValueError as error:
                    info.set(str(error))
                    return
                selected[0] = max(0, selected[0]-1)
                paint()
                info.set(f'{row_name(pet)} 已存入银行。')

            def withdraw(index=None):
                rows = entries()
                target = selected[0] if index is None else index
                if not 0 <= target < len(rows):
                    return
                where, pet = rows[target]
                if where != 'bank':
                    info.set('请选择银行中的宠物再取出。')
                    return
                try:
                    state.move_pet(pet.uid, to_bank=False)
                except ValueError as error:
                    info.set(str(error))
                    return
                selected[0] = max(0, target-1)
                paint()
                info.set(f'{row_name(pet)} 已取出到队伍。')

            def row_name(pet):
                return self.data.tables['Pet'][pet.species]['name']

            def wheel(event):
                rows = entries()
                step = -4 if event.delta > 0 else 4
                scroll[0] = min(max(0, len(rows)-8), max(0, scroll[0]+step))
                paint()

            if hasattr(self, 'ui_art_label'):
                self.ui_art_label.bind('<MouseWheel>', wheel)
            paint()
            info.set(f'携带 {len(state.pets)}/{state.pet_capacity()} · '
                     f'银行 {len(state.bank)}/{state.pet_capacity(True)}')

    def _cards_body(self, body, info):
        """Original CardLegendUI shell; the card battle rules are still being ported."""
        body.pack_forget()
        layer = self.cocos_ui.render('CardLegendUI', (800, 480), {})
        self.ui_base_layer = layer
        self.ui_hits = dict(self.cocos_ui.hits)
        self.ui_rects = dict(self.cocos_ui.rects)
        self.ui_buttons = dict(self.cocos_ui.buttons)
        self.ui_button_text = dict(self.cocos_ui.button_text)
        self.ui_actions['open_Button'] = lambda: info.set(
            '卡牌传说规则仍在按手机版原逻辑接入，当前不会伪造开包结果。')
        self.ui_actions['close_Button'] = self.close_ui
        info.set('卡牌传说 · 原版界面')
        if getattr(self, 'ui_art_label', None) is not None:
            photo = ImageTk.PhotoImage(layer)
            self.ui_art_label.configure(image=photo)
            self.ui_art_label.image = photo
    
    def _roulette_body(self, body, info):
        activity = Activities(self.state)
        body.pack_forget()
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
        self.ui_actions['close_Button'] = self.close_ui
        refresh()

    def lottery_ui(self, force=False):
        if not force and (self.battle or self.runtime.running or self.ui_open):
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
                if pets:
                    self.open_lucky_pet_info(pets[0].uid, back='lottery')
            except (ValueError, KeyError) as error:
                info.set(str(error))
        buttons = tk.Frame(win)
        buttons.pack(pady=8)
        for title, command in [('免费抽宠', lambda: draw(1, True)), ('普通抽宠', lambda: draw(1)),
                               ('黄金抽宠', lambda: draw(2)), ('黄金三连', lambda: draw(3))]:
            tk.Button(buttons, text=title, command=command).pack(side='left', padx=5)
        tk.Button(buttons, text='关闭', command=self.close_ui).pack(side='left', padx=5)
