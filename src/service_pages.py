"""Populate original bank and skill prefabs before publishing a single frame."""
from game_state import numbers
from pet_appearance import quality_color


class ServicePages:
    def _service_pet_card(self, page, pet, at, prefix, area, selected=False):
        row = self.data.tables['Pet'][pet.species]
        stats = pet.stats(self.data.tables)
        page.add('PetSelectItemUI', at, prefix=prefix, clip=area,
                 colors={'name_Text': quality_color(pet)},
                 text={'name_Text': row['name'], 'lv_BitmapFontLabel': str(pet.level),
                       'hpHave_BitmapFontLabel': str(pet.hp), 'hpMax_BitmapFontLabel': str(stats[0]),
                       'enHave_BitmapFontLabel': str(pet.energy), 'enMax_BitmapFontLabel': str(stats[1]),
                       'friendly_BitmapFontLabel': str(pet.friendly)},
                 resources={'kind_Image': 'UI/'+self.data.tables['PetKindEnum'][row['kind']]['iconTexture']},
                 visible={'selected_Image': selected})

    def _service_party_picker(self, callback, back):
        from original_pages import Page
        offset = [0]
        pets = list(self.state.pets)
        stride = 74+self._list_margin('PetSelectUI', 'pet_ListView')

        def paint():
            page = Page(self, 'PetSelectUI')
            area = page.rects['Layer/root_Panel/pet_ListView']
            for i, pet in enumerate(pets):
                x, y = round(area[0]), round(area[1]+i*stride-offset[0])
                if y+74 <= area[1] or y >= area[3]:
                    continue
                self._service_pet_card(page, pet, (x, y), f'bank_deposit_{i}/', area)
                page.hit(f'bank_deposit_{i}', (x, y, x+309, y+74), lambda p=pet: callback(p), area)
            page.actions['close_Button'] = back
            self._page_wheel(wheel)
            page.publish()

        def wheel(event):
            offset[0] = max(0, min(max(0, len(pets)*stride-320), offset[0]+(-74 if event.delta > 0 else 74)))
            paint()
        paint()

    def _service_bank_page(self, info):
        from original_pages import Page
        offset, selected = [0], [None]
        stride = 153+self._list_margin('PetBankUI', 'pets_ListView')

        def paint():
            pets = list(self.state.bank)
            offset[0] = max(0, min(max(0, len(pets)*stride-512), offset[0]))
            page = Page(self, 'PetBankUI', text={**self._money_text(),
                        'progress_BitmapFontLabel': f'{len(pets)}/{self.state.pet_capacity(True)}',
                        'info_Text': '请选择银行宠物取回；点击寄存可选择随身宠物。'},
                        resources=self._money_icons())
            area = page.rects['Layer/root_Panel/pets_ListView']
            for i, pet in enumerate(pets):
                x, y = round(area[0]+i*stride-offset[0]), round(area[1])
                if x+153 <= area[0] or x >= area[2]:
                    continue
                row = self.data.tables['Pet'][pet.species]
                kind = self.data.tables['PetKindEnum'][row['kind']]
                page.add('PetBankItemUI', (x, y), prefix=f'bank_{i}/', clip=area,
                         colors={'name_Text': quality_color(pet)},
                         text={'name_Text': row['name'], 'lv_BitmapFontLabel': str(pet.level)},
                         resources={'kindIcon_Image': 'UI/'+kind['iconTexture'], 'kind_Image': 'UI/'+kind['texture']},
                         visible={'selected_Image': pet.uid == selected[0], 'petPos_Image': False},
                         actions={'getBack_Button': lambda p=pet: withdraw(p)})
                page.animated_pets.append((pet.species, (x+76.5, y+165),
                    (max(area[0], x+4), y+15, min(area[2], x+149), min(area[3], y+170)), 100))
                page.hit(f'bank_card_{i}', (x, y+20, x+153, y+175), lambda p=pet: select(p), area)
            page.actions.update({'consign_Button': deposit_picker, 'close_Button': self.close_ui})
            self._page_wheel(wheel)
            page.publish()

        def select(pet):
            selected[0] = pet.uid
            paint()

        def deposit_picker():
            self._service_party_picker(deposit, paint)

        def deposit(pet):
            try:
                self.state.move_pet(pet.uid, to_bank=True)
            except ValueError as error:
                self._page_tip(str(error), deposit_picker)
                return
            selected[0] = pet.uid
            offset[0] = max(0, len(self.state.bank)*stride-512)
            paint()

        def withdraw(pet):
            try:
                self.state.move_pet(pet.uid, to_bank=False)
            except ValueError as error:
                self._page_tip(str(error), paint)
                return
            paint()

        def wheel(event):
            offset[0] += -stride if event.delta > 0 else stride
            paint()
        paint()

    def _service_skill_page(self, info):
        from original_pages import Page
        selected, pet_offset, skill_offset = [0], [0], [0]

        def choices(pet):
            rows = [(str(k), None) for k in numbers(self.data.tables['Pet'][pet.species]['skillIds'])]
            rows += [(str(row['skillId']), kid) for kid, row in self.data.tables['SkillItem'].items()
                     if self.state.count(kid) > 0]
            return rows

        def learn(pet, key, scroll):
            self.open_skill_learn_confirm(pet.uid, key, scroll=scroll, replace=None, back=6)

        def paint():
            pets = self.state.pets
            selected[0] = min(selected[0], max(0, len(pets)-1))
            page = Page(self, 'SkillLearnUI', text=self._money_text(), resources=self._money_icons())
            left = page.rects['Layer/root_Panel/petList_Panel/pet_ListView']
            right = page.rects['Layer/root_Panel/skillListBg_Image/skillList_Panel/skill_ListView']
            for i, pet in enumerate(pets):
                x, y = round(left[0]), round(left[1]+i*110-pet_offset[0])
                if y+110 <= left[1] or y >= left[3]:
                    continue
                row = self.data.tables['Pet'][pet.species]
                stats = pet.stats(self.data.tables)
                page.add('PetListItemUI', (x, y), prefix=f'skill_pet_{i}/', clip=left,
                         colors={'name_Text': quality_color(pet)},
                         text={'name_Text': row['name'], 'lv_BitmapFontLabel': str(pet.level),
                               'hpHave_BitmapFontLabel': str(pet.hp), 'hpMax_BitmapFontLabel': str(stats[0]),
                               'enHave_BitmapFontLabel': str(pet.energy), 'enMax_BitmapFontLabel': str(stats[1]),
                               'friendly_BitmapFontLabel': str(pet.friendly)},
                         resources={'kind_Image': 'UI/'+self.data.tables['PetKindEnum'][row['kind']]['iconTexture']},
                         visible={'add_Panel': False, 'selected_Image': i == selected[0]})
                page.hit(f'skill_pet_{i}', (x, y, x+361, y+110), lambda index=i: choose(index), left)
            entries = choices(pets[selected[0]]) if pets else []
            skill_offset[0] = max(0, min(max(0, len(entries)*67-(right[3]-right[1])), skill_offset[0]))
            for i, (key, scroll) in enumerate(entries):
                pet = pets[selected[0]]
                row = self.data.tables['Skill'].get(key) or self.data.tables['Talent'].get(key)
                if not row:
                    continue
                x, y = round(right[0]), round(right[1]+i*67-skill_offset[0])
                if y+67 <= right[1] or y >= right[3]:
                    continue
                learned = key in pet.skills or key in pet.talents
                money = self.data.tables['Money'].get(str(row.get('moneyId')), {})
                icon = self._item_data(scroll)[1] if scroll else 'UI/'+money.get('littleIconTexture', 'money_little_icon_gold.png')
                page.add('SkillLearnItemUI', (x, y), prefix=f'skill_row_{i}/', clip=right,
                         text={'skillName_Text': row['name'], 'energy_BitmapFontLabel': str(row.get('energyCost', 0)),
                               'cost_BitmapFontLabel': 'x1' if scroll else 'x'+str(row.get('moneyCount', 0))},
                         resources={'cost_Image': icon},
                         visible={'learn_Button': not learned, 'change_Button': False, 'already_Image': learned,
                                  'energy_Text': key in self.data.tables['Skill'],
                                  'energy_BitmapFontLabel': key in self.data.tables['Skill']},
                         actions={'learn_Button': lambda p=pet, k=key, item=scroll: learn(p, k, item)})
            page.actions['close_Button'] = self.close_ui
            self._page_wheel(wheel)
            page.publish()
            info.set('选择宠物与技能；左右列表均可滚动。')

        def choose(index):
            selected[0], skill_offset[0] = index, 0
            paint()

        def wheel(event):
            if getattr(event, 'x', 500) < 410:
                pet_offset[0] = max(0, min(max(0, len(self.state.pets)*110-328),
                    pet_offset[0]+(-110 if event.delta > 0 else 110)))
            else:
                skill_offset[0] += -67 if event.delta > 0 else 67
            paint()
        paint()
