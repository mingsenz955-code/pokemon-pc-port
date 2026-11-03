"""Compose the original pet cards and bounded skill/talent descriptions."""
from PIL import Image, ImageDraw
from event_runtime import Request
from economy import EVOLUTION_GOLD_COST


def text_box(page, rect, value, font, offset=0):
    """Wrap complete text and crop only the viewport; scrolling keeps it readable."""
    w, h = max(1, round(rect[2]-rect[0])), max(1, round(rect[3]-rect[1]))
    probe = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    lines, line = [], ''
    import re
    for char in re.sub(r'#[0-9]', '', str(value)):
        if char == '\n' or probe.textlength(line+char, font=font) > w:
            lines.append(line)
            line = '' if char == '\n' else char
        else:
            line += char
    lines.append(line)
    full = Image.new('RGBA', (w, max(h, len(lines)*(font.size+3))))
    draw = ImageDraw.Draw(full)
    for i, line in enumerate(lines):
        draw.text((0, i*(font.size+3)), line, font=font, fill='#693100', anchor='lt')
    offset = max(0, min(round(offset), full.height-h))
    page.layer.alpha_composite(full.crop((0, offset, w, offset+h)), (round(rect[0]), round(rect[1])))
    return max(0, full.height-h)


class PetPages:
    def _trial_pet_page(self, body, info):
        from original_pages import Page
        body.pack_forget()
        key = str(self.ui_parameters.get('par1', '600001'))
        row = self.data.tables['TrialPet'].get(key)
        if row is None:
            self._page_tip('找不到这位宠物使者对应的宠物。', self.close_ui)
            return
        def paint():
            current = next((p for p in self.state.pets if p.trial_id == key), None)
            pet = current or self.state.preset_pet(key, 'TrialPet')
            text, visible, resources = self._pet_base_fields(pet)
            text['lv_BitmapFontLabel'] = str(pet.level)
            purchased = self.state.trial_pet_purchased(key)
            can_trial = not purchased and int(row['trialCount']) > 0 and key not in self.state.activities.get('trial_received', [])
            text['tips_Text'] = ('已永久购买。' if purchased else f'剩余试用 {current.trial_remaining} 场战斗。' if current else
                                 f'可试用 {row["trialCount"]} 场战斗。' if can_trial else '这只宠物没有剩余免费试用次数。')
            store = self.data.tables['Store'][row['storeId']]
            text['costTip_Text'] = '已购买' if purchased else store.get('des2', '')
            visible.update({'buy_Button': not purchased, 'trial_Button': not purchased and (can_trial or bool(current)), 'cost_BitmapFontLabel': False,
                            'number_BitmapFontLabel': False, 'evolutionTimes_BitmapFontLabel': pet.species in self.data.tables['Evolution'],
                            'trial_Image': not bool(current)})
            page = Page(self, 'TrialPetUI', timeline_frame=60, text=text, visible=visible, resources=resources)
            self._pet_base_art(page, pet)
            if current:
                rect = next(r for k, r in page.rects.items() if k.endswith('/trial_Button'))
                ImageDraw.Draw(page.layer).text(((rect[0]+rect[2])/2, (rect[1]+rect[3])/2),
                    '归还', font=self.cocos_ui.font('', 20), anchor='mm', fill='#693100')
            page.actions.update({'trial_Button': take_or_return, 'buy_Button': buy, 'close_Button': self.close_ui})
            page.publish()
        def take_or_return():
            current = next((p for p in self.state.pets if p.trial_id == key), None)
            if current:
                self.state.pets.remove(current)
                self.state.active_pet = min(self.state.active_pet, max(0, len(self.state.pets)-1))
                self.close_ui('yes')
                return
            try:
                self.state.receive_trial_pet(key)
            except ValueError as error:
                self._page_tip(str(error), paint)
                return
            self.close_ui('yes')
        def buy():
            store = self.data.tables['Store'][row['storeId']]
            money = self.data.tables['Money'][store['costMoneyType']]['name']
            def confirm():
                try:
                    pet = self.state.buy_trial_pet(key)
                except ValueError as error:
                    self._page_tip(str(error), paint)
                    return
                self.reward_overlay([(pet.species, 1)], back=paint, title='获得宠物', underlay=False)
            self._choice_page(f"花费 {store['costCount']} {money}购买这只永久宠物？", confirm, paint)
        paint()

    def _evolution_page(self, body, info):
        from original_pages import Page
        from game_state import numbers
        body.pack_forget()
        uid = str(self.ui_parameters.get('uid', ''))
        pet = next((p for p in self.state.pets if p.uid == uid), None)
        if pet is None:
            self._page_tip('请选择携带的宠物。', self.close_ui)
            return
        row = self.data.tables['Evolution'].get(pet.species)
        def back():
            self.open_ui(Request('openui', 'evolution-return', 0, {'parameters': {'uiid': 47}}))
        if not row:
            self._page_tip('这只宠物没有下一阶段进化。', back)
            return
        name = self.data.tables['Pet'][pet.species]['name']
        target = str(row['petId'])
        def paint():
            ready = pet.level >= int(row['level'])
            page = Page(self, 'EvolutionConditionUI', timeline_frame=60,
                        text={'petName_Text': name}, auto_text=('petName_Text',),
                        visible={'costTip_Text': False, 'cost_BitmapFontLabel': False,
                                 'moneyIcon_Image': False, 'image_evolution_what_1': False,
                                 'titleCanEvolution_Sprite': ready, 'evolution_Image': True})
            if not ready:
                rect = (290, 161, 594, 183)
                text_box(page, rect, '未满足进化条件', self.cocos_ui.font('', 16))
            requirements = [('等级', pet.level, int(row['level']))]
            requirements += [(self._item_data(str(k))[0], self.state.count(k), n)
                             for k, n in zip(numbers(row['itemIds']), numbers(row['itemCounts']))]
            for i, (label, have, need) in enumerate(requirements):
                page.add('ConditionItemUI', (288, 188+i*23), size=(304, 22),
                         prefix=f'evolution_condition_{i}/', clip=(288, 186, 592, 293),
                         text={'name_Text': label, 'have_BitmapFontLabel': str(have),
                               'need_BitmapFontLabel': str(need)}, sizes={'name_Text': (110, 22)})
            page.animated_pets.extend([(pet.species, (348, 363), (280, 295, 415, 365), 70),
                                       (target, (538, 363), (470, 295, 608, 365), 70)])
            page.actions.update({'evolution_Button': evolve, 'close_Button': back})
            rect = (490, 430, 700, 467)
            ImageDraw.Draw(page.layer).rounded_rectangle(rect, radius=12, fill='#06b7df', outline='#fff2bd', width=2)
            ImageDraw.Draw(page.layer).text((595, 448), f'金币进化 {EVOLUTION_GOLD_COST}', font=self.cocos_ui.font('', 18), anchor='mm', fill='white')
            page.hit('gold_evolution', rect, lambda: self._choice_page(
                f'花费 {EVOLUTION_GOLD_COST} 金币进化？仍需达到等级，不消耗进化材料。', lambda: evolve(True), paint))
            page.publish()
        def evolve(use_gold=False):
            before = pet.stats(self.data.tables)
            try:
                self.state.evolve(uid, use_gold=use_gold)
            except ValueError as error:
                self._page_tip(str(error), paint)
                return
            after = pet.stats(self.data.tables)
            fields = {'name_Text': self.data.tables['Pet'][pet.species]['name']}
            for label, old, new in zip(('Life', 'Energy', 'Strength', 'Defense', 'Speed'), before, after):
                fields['arrt'+label+'_BitmapFontLabel'] = str(old)
                fields['arrt'+label+'To_BitmapFontLabel'] = str(new)
            stars = int(self.data.tables['Pet'][pet.species]['starLevel'])
            page = Page(self, 'PetEvolutionEffectUI', timeline_frame=180, text=fields,
                        visible={'weixin_Button': False, **{f'star_Sprite_{i}': i <= stars for i in range(1, 6)}})
            page.animated_pets.append((pet.species, (400, 300), (230, 60, 580, 310), 175))
            page.actions.update({'confirm_Button': back, 'close_Button': back})
            page.publish()
        paint()

    def _pet_base_fields(self, pet):
        row = self.data.tables['Pet'][pet.species]
        visibility = {'trialState_Panel': False, 'trialTimes_Panel': False,
                      'cantEvolution_Sprite': pet.species not in self.data.tables['Evolution'],
                      'evolutionTimes_Sprite': pet.species in self.data.tables['Evolution']}
        for i in range(1, 7):
            visibility[f'heart_Sprite_{i}'] = pet.friendly >= i
        for i in range(1, 6):
            visibility[f'star_Sprite_{i}'] = int(row['starLevel']) >= i
        text = {'name_Text': row['name'], 'number_BitmapFontLabel': str(int(pet.species)-100000),
                'lv_BitmapFontLabel': str(pet.level), 'evolutionTimes_BitmapFontLabel': row['evolutionCount']}
        if pet.trial_id:
            text['name_Text'] += f'·试用{pet.trial_remaining}'
        kind = self.data.tables['PetKindEnum'][row['kind']]
        resources = {'kindIcon_Sprite': 'UI/'+kind['iconTexture'], 'kind_Sprite': 'UI/'+kind['texture'],
                     'landType_Sprite': 'UI/'+self.data.tables['PetLandType'][row['landType']]['texture']}
        contrast = self.data.tables['Contrast'][row['restraint']]
        from game_state import numbers
        strong = [str(i+1) for i, value in enumerate(numbers(contrast['mutual'])) if value > 100 and str(i+1) in self.data.tables['PetKindEnum']]
        visibility['restraint_Sprite'] = bool(strong)
        visibility['restraintName_Sprite'] = bool(strong)
        if strong:
            resources['restraint_Sprite'] = 'UI/'+self.data.tables['PetKindEnum'][strong[0]]['texture']
        return text, visibility, resources

    def _pet_base_art(self, page, pet):
        stats = pet.stats(self.data.tables)
        area = next((r for k, r in page.rects.items() if k.endswith('/baseInfo_Panel')), None)
        point = next((r for k, r in page.rects.items() if k.endswith('/petPos_Node')), None)
        art = self.data.pet_image(pet.species)
        if art is not None and area and point:
            page.animated_pets.append((pet.species, point, area, 145))
        for suffix, attributes in [('property_ListView_1', [1, 3, 5]), ('property_ListView_2', [2, 4])]:
            area = next((r for k, r in page.rects.items() if k.endswith('/'+suffix)), None)
            if not area:
                continue
            for i, attribute in enumerate(attributes):
                value = str(stats[attribute-1])
                if attribute == 1:
                    value = f'{pet.hp}/{stats[0]}'
                elif attribute == 2:
                    value = f'{pet.energy}/{stats[1]}'
                page.add('PetPropertyItemUI', (round(area[0]), round(area[1]+i*21)),
                         prefix=f'attribute_{attribute}/', clip=area, size=(round(area[2]-area[0]), 20),
                         text={'pro_BitmapFontLabel': value},
                         resources={'name_Image': 'UI/'+self.data.tables['PetAttributeEnum'][str(attribute)]['texture']})

    def _pet_property_page(self, body, info):
        from original_pages import Page
        body.pack_forget()
        pet = next((p for p in self.state.pets if p.uid == str(self.ui_parameters.get('uid'))), None)
        if pet is None:
            self._page_tip('这只宠物不在携带栏。', self.close_ui)
            return
        info.set(self.data.tables['Pet'][pet.species]['name'])
        tab, selected, scroll, limit = ['skill'], [0], [0], [0]
        list_scroll, list_area, list_limit = [0], [None], [0]
        def paint():
            text, visible, resources = self._pet_base_fields(pet)
            visible.update({'infoSkill_Panel': tab[0] == 'skill', 'infoTalent_Panel': tab[0] == 'talent',
                            'infoTalent_ListView': tab[0] == 'talent',
                            'skillTag_Button/selected_Sprite': tab[0] == 'skill',
                            'skillTag_Button/unselected_Sprite': tab[0] != 'skill',
                            'talentTag_Button/selected_Sprite': tab[0] == 'talent',
                            'talentTag_Button/unselected_Sprite': tab[0] != 'talent',
                            'evolution_Particle': False, 'Particle_1': False, 'Particle_2': False})
            text['skillInfo_Text'] = ''
            from game_formulas import level_exp
            page = Page(self, 'PetPropertyUI', text=text, visible=visible, resources=resources,
                        percentages={'exp_LoadingBar': min(1, pet.exp/max(1, level_exp(pet.level)))})
            self._pet_base_art(page, pet)
            rows = [self.data.tables['Skill' if tab[0] == 'skill' else 'Talent'][str(k)]
                    for k in (pet.skills if tab[0] == 'skill' else pet.talents)]
            area = next(r for k, r in page.rects.items() if k.endswith('/info'+('Skill' if tab[0] == 'skill' else 'Talent')+'_ListView'))
            list_area[0], list_limit[0] = area, max(0, len(rows)*25.5-(area[3]-area[1]))
            for i, row in enumerate(rows):
                x, y = round(area[0]), round(area[1]+i*25.5-list_scroll[0])
                if y+25.5 <= area[1] or y >= area[3]:
                    continue
                page.add('PetListSkillItemUI', (x, y), prefix=f'pet_skill_{i}/', clip=area,
                         text={'name_Text': row['name'], 'cost_BitmapFontLabel': str(row.get('energyCost', ''))},
                         visible={'selected_Image': i == selected[0], 'energy_Text': tab[0] == 'skill',
                                  'cost_BitmapFontLabel': tab[0] == 'skill'})
                page.hit(f'pet_skill_{i}', (x, y, area[2], y+25.5), lambda v=i: choose(v), area)
            detail = rows[min(selected[0], len(rows)-1)].get('des', '') if rows else ''
            bounds = next(r for k, r in page.rects.items() if k.endswith('/skillInfo_Text'))
            limit[0] = text_box(page, bounds, detail, self.cocos_ui.font('', 16), scroll[0])
            self.pet_description = {'text': detail, 'bounds': bounds, 'scroll_limit': limit[0]}
            page.actions.update({'skillTag_Button': lambda: change('skill'), 'talentTag_Button': lambda: change('talent'),
                                 'free_Button': lambda: self.open_free_pet(pet.uid, back=57),
                                 'evolution_Button': lambda: self.open_evolution(pet.uid, back=57),
                                 'close_Button': self.pets_ui})
            page.publish()
            self._page_wheel(wheel)
        def choose(value):
            selected[0], scroll[0] = value, 0
            paint()
        def change(value):
            tab[0], selected[0], scroll[0] = value, 0, 0
            list_scroll[0] = 0
            paint()
        def wheel(event):
            area = list_area[0]
            if area and area[0] <= getattr(event, 'x', -1) <= area[2] and area[1] <= getattr(event, 'y', -1) <= area[3]:
                list_scroll[0] = max(0, min(list_limit[0], list_scroll[0]+(-26 if event.delta > 0 else 26)))
            else:
                scroll[0] = max(0, min(limit[0], scroll[0]+(-24 if event.delta > 0 else 24)))
            paint()
        paint()

    def _pet_list_page(self, body, info):
        from original_pages import Page
        body.pack_forget()
        selected, offset = [min(self.state.active_pet, max(0, len(self.state.pets)-1))], [0]
        train = [False]
        def paint():
            pets = self.state.pets
            pet = pets[min(selected[0], len(pets)-1)] if pets else None
            text, visible, resources = self._pet_base_fields(pet) if pet else ({}, {}, {})
            text['progress_BitmapFontLabel'] = f'{len(pets)}/{self.state.pet_capacity()}'
            visible.update({'baseInfo_Panel': bool(pet) and not train[0], 'skillInfo_Panel': False, 'train_ProjectNode': bool(pet) and train[0],
                            'evolution_Particle': False, 'Particle_1': False, 'Particle_2': False})
            from game_formulas import level_exp
            percentages = {'exp_LoadingBar': min(1, pet.exp/max(1, level_exp(pet.level)))} if pet else {}
            if pet and train[0]:
                from game_formulas import train_hp, train_mp, train_attribute
                text['allTrain_BitmapFontLabel'] = f'{sum(pet.training)}/2000'
                percentages['all_LoadingBar'] = sum(pet.training)/2000
                for i, name in enumerate(('life', 'energy', 'strength', 'defense', 'speed')):
                    value = pet.training[i]
                    text[f'{name}Train_BitmapFontLabel'] = f'{value}/1000'
                    text[f'addTrain_{name}_BitmapFontLabel'] = f'+{(train_hp if i == 0 else train_mp if i == 1 else train_attribute)(value)}'
                    percentages[f'{name}_LoadingBar'] = value/1000
            page = Page(self, 'PetListUI', text=text, visible=visible, resources=resources, percentages=percentages, timeline_frame=60)
            area = next(r for k, r in page.rects.items() if k.endswith('/item_ListView'))
            for i, member in enumerate(pets):
                x, y = round(area[0]+20), round(area[1]+i*110-offset[0])
                if y+110 <= area[1] or y >= area[3]:
                    continue
                row, stats = self.data.tables['Pet'][member.species], member.stats(self.data.tables)
                page.add('PetListItemUI', (x, y), prefix=f'pet_list_{i}/', clip=area,
                         text={'name_Text': row['name']+(f'·试用{member.trial_remaining}' if member.trial_id else ''), 'lv_BitmapFontLabel': str(member.level),
                               'hpHave_BitmapFontLabel': str(member.hp), 'hpMax_BitmapFontLabel': str(stats[0]),
                               'enHave_BitmapFontLabel': str(member.energy), 'enMax_BitmapFontLabel': str(stats[1]),
                               'friendly_BitmapFontLabel': str(member.friendly)},
                         visible={'add_Panel': False, 'selected_Image': i == selected[0],
                                   'joinBattleSign_Image': i == self.state.active_pet,
                                   'signTrial_Image': bool(member.trial_id)})
                page.hit(f'pet_row_{i}', (x, y, x+320, y+110), lambda v=i: choose(v), area)
            if pet:
                if not train[0]:
                    self._pet_base_art(page, pet)
                page.actions.update({'skill_Button': lambda: self.open_pet_property(pet.uid),
                                     'trainValue_Button': training,
                                     'free_Button': lambda: self.open_ui(Request('openui', 'return-trial', 0, {'parameters': {'uiid': 13, 'par1': pet.trial_id}})) if pet.trial_id else self.open_free_pet(pet.uid),
                                     'evolution_Button': lambda: self.open_evolution(pet.uid),
                                     'joinBattle_Button': lambda: join(selected[0]),
                                     'useItem_Button': lambda: item(pet)})
            page.actions['close_Button'] = self.close_ui
            page.publish()
            self._page_wheel(wheel)
        def choose(value):
            selected[0] = value
            paint()
        def training():
            train[0] = not train[0]
            paint()
        def join(value):
            if self.state.pets[value].trial_remaining == 0:
                self._page_tip('试用次数已用完，请到宠物使者处归还。', paint)
                return
            self.state.active_pet = value
            name = self.data.tables['Pet'][self.state.pets[value].species]['name']
            info.set(f'已设置 {name} 为参战宠物。')
            paint()
        def item(pet):
            def apply(kid):
                try:
                    self.state.use_item(kid, pet)
                except ValueError as error:
                    self._page_tip(str(error), paint)
                    return
                paint()
            keys = {k for k in self.data.tables['PetItem'] if int(self.data.tables['Item'][k]['useType']) in (1, 2)}
            self._bag_page(info, allowed_keys=keys, select_item=apply, back=paint)
        def wheel(event):
            offset[0] = max(0, min(max(0, len(self.state.pets)*110-328), offset[0]+(-55 if event.delta > 0 else 55)))
            paint()
        paint()
