"""Original HatchRoomUI cards, HatchCheckUI conditions and PetHatchEffectUI."""
from activities import Activities
from game_state import numbers, Pet
import time


class HatchPages:
    def _hatch_room_page(self, info, selected=0, offset=0):
        from original_pages import Page
        activity = Activities(self.state)
        eggs = self.state.activities.get('eggs', {})
        stride = 153+self._list_margin('HatchRoomUI', 'pets_ListView')
        offset = max(0, min(10*stride-512, offset))
        self.hatch_selection = selected
        self.hatch_offset = offset
        page = Page(self, 'HatchRoomUI', text={**self._money_text(),
                    'progress_BitmapFontLabel': f'{len(eggs)}/10'}, resources=self._money_icons())
        area = next(r for k, r in page.rects.items() if k.endswith('/pets_ListView'))
        for index in range(10):
            x, y = round(area[0]+index*stride-offset), round(area[1])
            if x+153 <= area[0] or x >= area[2]:
                continue
            egg = eggs.get(str(index))
            hatched = bool(egg and egg.get('pet'))
            ready = bool(egg and not hatched and self._hatch_ready(index))
            pet = Pet(**egg['pet']) if hatched else None
            name = self.data.tables['Pet'][pet.species]['name'] if pet else self._item_data(egg['item'])[0] if egg else ''
            resources = {}
            if egg and not hatched:
                resources['petPos_Image'] = self._item_data(egg['item'])[1]
            if pet:
                kind = self.data.tables['PetKindEnum'][self.data.tables['Pet'][pet.species]['kind']]
                resources.update({'kindIcon_Image': 'UI/'+kind['iconTexture'], 'kind_Image': 'UI/'+kind['texture']})
            page.add('HatchItemUI', (x, y), prefix=f'hatch_{index}/', clip=area,
                     text={'name_Text': name}, resources=resources,
                     sizes={'petPos_Image': (85, 85)}, positions={'petPos_Image': (76.5, 137)},
                     visible={'selected_Image': False, 'putIn_Button': not egg, 'hatch_Button': ready,
                              'check_Button': bool(egg) and not ready and not hatched, 'takeBack_Button': hatched,
                              'hatchLight_Image': ready, 'hatchingLight_Image': bool(egg) and not hatched and not ready,
                              'hatchedLight_Image': hatched, 'petPos_Image': bool(egg) and not hatched,
                              'kindIcon_Image': hatched, 'kind_Image': hatched},
                     actions={'putIn_Button': lambda i=index: self._hatch_choose_egg(info, i),
                              'check_Button': lambda i=index: self._hatch_check_page(info, i),
                              'hatch_Button': lambda i=index: self._hatch_do(info, i, False),
                              'takeBack_Button': lambda i=index: self._hatch_take(info, i)})
            page.hit(f'hatch_card_{index}', (x, y, x+153, y+180),
                     lambda i=index: self._hatch_check_page(info, i), area)
            if pet:
                page.animated_pets.append((pet.species, (x+76.5, y+140),
                    (max(area[0], x+5), y+5, min(area[2], x+148), y+145), 63))
        page.actions['close_Button'] = self.close_ui
        self.ui_window.protocol('WM_DELETE_WINDOW', self.close_ui)
        def wheel(event):
            self._hatch_room_page(info, selected, offset+(-stride if event.delta > 0 else stride))
        self._page_wheel(wheel)
        page.publish()

    def _hatch_ready(self, index):
        egg = self.state.activities.get('eggs', {}).get(str(index))
        if not egg or egg.get('pet'):
            return False
        row = self.data.tables['HatchItem'][egg['item']]
        return egg['exp'] >= int(row['exp']) and all(self.state.count(k) >= n for k, n in
            zip(numbers(row['itemIds']), numbers(row['itemCounts'])))

    def _hatch_choose_egg(self, info, index):
        back = lambda: self._hatch_room_page(info, index, getattr(self, 'hatch_offset', 0))
        keys = {k for k in self.data.tables['HatchItem'] if self.state.count(k) > 0}
        if not keys:
            self._page_tip('背包中没有可放入的宠物蛋。', back)
            return
        def put(key):
            try:
                Activities(self.state).put_egg(index, key)
            except ValueError as error:
                self._page_tip(str(error), back)
                return
            back()
        self._bag_page(info, allowed_keys=keys, select_item=put, back=back)

    def _hatch_check_page(self, info, index):
        from original_pages import Page
        egg = self.state.activities.get('eggs', {}).get(str(index))
        if not egg:
            self._hatch_choose_egg(info, index)
            return
        if egg.get('pet'):
            self._hatch_take(info, index)
            return
        row = self.data.tables['HatchItem'][egg['item']]
        ready = self._hatch_ready(index)
        self._hatch_room_page(info, index, getattr(self, 'hatch_offset', 0))
        room = self.original_page
        page = Page(self, 'HatchRoomUI', text={**self._money_text(),
                    'progress_BitmapFontLabel': f'{len(self.state.activities.get("eggs", {}))}/10'},
                    resources=self._money_icons())
        page.layer = room.display_frame.copy()
        page.hits, page.buttons, page.actions = {}, {}, {}
        page.add('HatchCheckUI', (0, 0), size=(800, 480), prefix='check/',
                 text={'cost_BitmapFontLabel': str(row['moneyCount'])},
                 visible={'hatch_Button': ready, 'moneyHatch_Button': not ready},
                 resources={'money_Image': 'UI/'+self.data.tables['Money'][row['moneyId']]['littleIconTexture']},
                 actions={'hatch_Button': lambda: self._hatch_do(info, index, False),
                          'moneyHatch_Button': lambda: self._hatch_do(info, index, True),
                          'takeBackEgg_Button': lambda: self._choice_page('取回宠物蛋？孵化经验将清零。',
                              lambda: self._hatch_take(info, index), lambda: self._hatch_check_page(info, index)),
                          'close_Button': lambda: self._hatch_room_page(info, index, getattr(self, 'hatch_offset', 0))})
        area = next(r for k, r in page.rects.items() if k.endswith('/condition_ListView'))
        requirements = [('孵化经验', egg['exp'], int(row['exp']))]
        requirements += [(self._item_data(k)[0], self.state.count(k), n)
                         for k, n in zip(numbers(row['itemIds']), numbers(row['itemCounts']))]
        for i, (name, have, need) in enumerate(requirements):
            page.add('ConditionItemUI', (area[0], area[1]+i*25), size=(336, 21),
                     prefix=f'condition_{i}/', clip=area,
                     text={'name_Text': name, 'have_BitmapFontLabel': str(have), 'need_BitmapFontLabel': str(need)})
        from pet_pages import text_box
        money_name = self.data.tables['Money'][row['moneyId']]['name']
        text_box(page, (area[0], area[3]-46, area[2], area[3]),
                 f'材料孵化：需要上面的经验和材料。\n金币直孵：{row["moneyCount"]}{money_name}，免经验和材料。',
                 self.cocos_ui.font('', 13))
        self._page_wheel(None)
        self.ui_window.protocol('WM_DELETE_WINDOW', lambda: self._hatch_room_page(info, index, getattr(self, 'hatch_offset', 0)))
        page.publish()

    def _hatch_do(self, info, index, use_money):
        try:
            pet = Activities(self.state).hatch(index, use_money=use_money)
        except ValueError as error:
            self._page_tip(str(error), lambda: self._hatch_check_page(info, index))
            return
        self._hatch_effect_page(info, index, pet)

    def _hatch_take(self, info, index):
        try:
            result = Activities(self.state).take_egg(index)
        except ValueError as error:
            self._page_tip(str(error), lambda: self._hatch_room_page(info, index, getattr(self, 'hatch_offset', 0)))
            return
        back = lambda: self._hatch_room_page(info, index, getattr(self, 'hatch_offset', 0))
        if result:
            self.reward_overlay([(result.species, 1)], back, underlay=False)
        else:
            back()

    def _hatch_effect_page(self, info, index, pet):
        from original_pages import Page
        fields = {'name_Text': self.data.tables['Pet'][pet.species]['name'], 'lv_BitmapFontLabel': str(pet.level)}
        for label, value in zip(('Life', 'Energy', 'Strength', 'Defense', 'Speed'), pet.stats(self.data.tables)):
            fields['arrt'+label+'_BitmapFontLabel'] = str(value)
        stars = int(self.data.tables['Pet'][pet.species]['starLevel'])
        args = dict(text=fields, visible={'weixin_Button': False,
                    **{f'star_Sprite_{i}': i <= stars for i in range(1, 6)}})
        page = Page(self, 'PetHatchEffectUI', timeline_frame=200, **args)
        events = {f['value']: f['frame'] for track in self.cocos_ui.layout('PetHatchEffectUI')['action']['tracks']
                  if track['property'] == 'FrameEvent' for f in track['frames']}
        page.pet_visible_after = events['showPet']/60
        info_after = events['showPetInfo']/60
        point = next(r for k, r in page.rects.items() if k.endswith('/petPos_Panel'))
        page.animated_pets.append((pet.species, point, (210, 60, 590, 315), 150))
        def frame_at(age):
            visible = dict(args['visible'], name_Panel=age >= info_after, info_Panel=age >= info_after)
            return self.cocos_ui.render('PetHatchEffectUI', (800, 480), text=fields, visible=visible,
                                        timeline_frame=min(200, int(age*60)))
        page.frame_at = frame_at
        page.actions['confirm_Button'] = lambda: (self._hatch_room_page(info, index, getattr(self, 'hatch_offset', 0))
                                                  if time.monotonic()-page.effect_start >= info_after else None)
        self._page_wheel(None)
        page.publish()
