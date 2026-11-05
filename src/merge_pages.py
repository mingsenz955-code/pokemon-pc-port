"""Original MergePetUI cards and bank selection, backed by PetMerge rules."""
from pet_appearance import quality_color


class MergePages:
    def _merge_page(self, info):
        from original_pages import Page
        base, materials = [None], [None]*6

        def recipe():
            return next((r for r in self.data.tables['PetMerge'].values()
                         if base[0] and int(r['petQuality']) == base[0].quality), None)

        def paint():
            self._page_wheel(None)
            self.cocos_ui.render('MergePetUI', (800, 480))
            rects = dict(self.cocos_ui.rects)
            hidden = {'Layer/root_Panel/mergePetNode': False}
            hidden.update({f'Layer/root_Panel/mergePetNodes_Panel/mergedPetNode_{i+1}': False for i in range(6)})
            row = recipe()
            page = Page(self, 'MergePetUI', timeline_frame=60, visible=hidden,
                        text={'cost_BitmapFontLabel': row['moneyCount'] if row else ''})

            def card(rect, pet, prefix, callback):
                visible = {'add_Button': pet is None, 'petPos_Image': False,
                           'namgBg_Image': pet is not None, 'lvBg_Image': pet is not None,
                           'kindIcon_Image': pet is not None, 'star_Panel': pet is not None,
                           'star_black_Panel': pet is not None, 'hatchedLight_Image': pet is not None,
                           'selected_Image': pet is base[0] and pet is not None}
                text, resources = {}, {}
                if pet:
                    data = self.data.tables['Pet'][pet.species]
                    kind = self.data.tables['PetKindEnum'][data['kind']]
                    text = {'name_Text': data['name'], 'lv_BitmapFontLabel': str(pet.level)}
                    resources = {'kindIcon_Image': 'UI/'+kind['iconTexture'], 'kind_Image': 'UI/'+kind['texture']}
                    visible.update({f'star_Sprite_{i}': pet.quality >= i for i in range(1, 6)})
                page.add('MergePetItemUI', (rect[0], rect[1]), prefix=prefix,
                         colors={'name_Text': quality_color(pet)} if pet else {},
                         visible=visible, text=text, resources=resources, actions={'add_Button': callback})
                page.hit(prefix.rstrip('/'), rect, callback)
                if pet:
                    page.animated_pets.append((pet.species, (rect[0]+59, rect[1]+125), rect, 86))

            card(rects['Layer/root_Panel/mergePetNode'], base[0], 'merge_base/', choose_base)
            for i in range(6):
                card(rects[f'Layer/root_Panel/mergePetNodes_Panel/mergedPetNode_{i+1}'],
                     materials[i], f'merge_mat_{i}/', lambda index=i: choose_material(index))
            page.actions.update({'add_Button': choose_base, 'autoAdd_Button': auto_add,
                                 'merge_Button': merge, 'close_Button': self.close_ui})
            if not any(k.endswith("/close_Button") for k in page.hits):
                self._add_page_close(page)
            page.publish()
            info.set('选择银行中的基础宠物与同品质材料。' if not row else
                     f'需要{row["petCount"]}只同品质、Lv.{row["petLevel"]}以上材料宠物，消耗{row["moneyCount"]}徽章。')

        def picker(callback, excluded):
            pets = [p for p in self.state.bank if p.uid not in excluded and not p.trial_id]
            if not pets:
                self._page_tip('银行中没有可选宠物，请先寄存宠物。', paint)
                return
            offset = [0]
            stride = 74+self._list_margin('PetSelectUI', 'pet_ListView')

            def show():
                page = Page(self, 'PetSelectUI')
                area = page.rects['Layer/root_Panel/pet_ListView']
                for i, pet in enumerate(pets):
                    x, y = round(area[0]), round(area[1]+i*stride-offset[0])
                    if y+74 <= area[1] or y >= area[3]:
                        continue
                    self._service_pet_card(page, pet, (x, y), f'merge_pick_{i}/', area)
                    page.hit(f'merge_pick_{i}', (x, y, x+309, y+74), lambda p=pet: callback(p), area)
                page.actions['close_Button'] = paint
                self._page_wheel(wheel)
                page.publish()

            def wheel(event):
                offset[0] = max(0, min(max(0, len(pets)*stride-320), offset[0]+(-74 if event.delta > 0 else 74)))
                show()
            show()

        def choose_base():
            picker(set_base, set())

        def set_base(pet):
            base[0], materials[:] = pet, [None]*6
            paint()

        def choose_material(index):
            row = recipe()
            if not row or index >= int(row['petCount']):
                self._page_tip('先选择基础宠物，只需放入当前配方要求的材料数量。', paint)
                return
            excluded = {base[0].uid} | {p.uid for i, p in enumerate(materials) if p and i != index}
            picker(lambda pet: set_material(index, pet), excluded)

        def set_material(index, pet):
            materials[index] = pet
            paint()

        def auto_add():
            row = recipe()
            if not row:
                self._page_tip('请先选择可融合的基础宠物。', paint)
                return
            eligible = [p for p in self.state.bank if p is not base[0] and not p.trial_id
                        and p.quality == base[0].quality and p.level >= int(row['petLevel'])]
            selected = eligible[:int(row['petCount'])]
            materials[:] = selected+[None]*(6-len(selected))
            paint()
            if len(selected) < int(row['petCount']):
                self._page_tip(f'符合条件的材料宠物不足：{len(selected)}/{row["petCount"]}。', paint)

        def merge():
            if not base[0]:
                self._page_tip('请先选择基础宠物。', paint)
                return
            try:
                result = self.state.merge_pets(base[0].uid, [p.uid for p in materials if p])
            except (ValueError, KeyError) as error:
                self._page_tip(str(error), paint)
                return
            base[0], materials[:] = result, [None]*6
            paint()
            self.save()
            self._page_tip(f'融合成功：{self.data.tables["Pet"][result.species]["name"]}，品质{result.quality}，成长属性提升。', paint)
        paint()
