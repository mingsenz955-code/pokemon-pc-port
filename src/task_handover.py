"""Native MultipleChoicePetUI for PlotEventItemCostTaskItem pet handovers."""
from event_runtime import Request
from task_costs import TaskCosts


class TaskHandover:
    def begin_task_handover(self, request):
        cost = TaskCosts(self.state, request.data['parameters'])
        if cost.committed() or not cost.pets:
            try:
                self.runtime.resume([])
                return True
            except ValueError as error:
                message = str(error)
        else:
            message = ''
        self.open_ui(Request('openui', 'task-pets', request.step, {'parameters': {'uiid': 50}}))
        self.ui_body.pack_forget()
        self.display_request = request
        groups, stage, selected, offset = list(cost.pets.items()), [0], {}, [0]

        def cancel():
            self.close_transient_ui()
            self.display_request, self.dialogue, self.runtime_error = None, None, ''
            self.runtime.abort('玩家取消任务交付，未提交任务')
            self.drive()

        def confirm():
            species, count = groups[stage[0]]
            if len(selected.get(species, [])) != count:
                self._page_tip(f'请选择 {count} 只{self.data.tables["Pet"][species]["name"]}。', paint)
                return False
            if stage[0]+1 < len(groups):
                stage[0] += 1
                offset[0] = 0
                paint()
                return
            try:
                self.runtime.resume([uid for uids in selected.values() for uid in uids])
            except ValueError as error:
                self._page_tip(str(error), paint)
                return False
            self.display_request = None
            self.close_transient_ui()
            self.drive()

        def paint():
            from original_pages import Page
            species, count = groups[stage[0]]
            pets = cost.candidates(species)
            page = Page(self, 'MultipleChoicePetUI', text={'title_Text':
                f'请选择{count}只{self.data.tables["Pet"][species]["name"]}'})
            area = next(r for k, r in page.rects.items() if k.endswith('/pet_ListView'))
            stride = 74+self._list_margin('MultipleChoicePetUI', 'pet_ListView')
            offset[0] = max(0, min(offset[0], max(0, len(pets)*stride-(area[3]-area[1]))))
            def toggle(pet):
                uids = selected.setdefault(species, [])
                if pet.uid in uids:
                    uids.remove(pet.uid)
                elif len(uids) < count:
                    uids.append(pet.uid)
                paint()
            for i, pet in enumerate(pets):
                x, y = area[0], round(area[1]+i*stride-offset[0])
                if y+74 <= area[1] or y >= area[3]:
                    continue
                row = self.data.tables['Pet'][pet.species]
                stats = pet.stats(self.data.tables)
                chosen = pet.uid in selected.get(species, [])
                page.add('MultipleChoicePetItemUI', (x, y), prefix=f'handin_{pet.uid}/', clip=area,
                         text={'name_Text': row['name'], 'lv_BitmapFontLabel': str(pet.level),
                               'hpHave_BitmapFontLabel': str(pet.hp), 'hpMax_BitmapFontLabel': str(stats[0])},
                         resources={'kind_Image': 'UI/'+self.data.tables['PetKindEnum'][row['kind']]['iconTexture']},
                         visible={'selected_Image': chosen, 'done_Image': chosen})
                page.hit(f'handin_pet_{pet.uid}', (x, y, x+309, y+74), lambda p=pet: toggle(p), area)
            page.actions.update({'confirm_Button': confirm, 'close_Button': cancel})
            page.publish()
            def wheel(event):
                offset[0] += -74 if event.delta > 0 else 74
                paint()
            self._page_wheel(wheel)
            self.ui_window.protocol('WM_DELETE_WINDOW', cancel)

        if message:
            self._page_tip(message, cancel)
            self.ui_window.protocol('WM_DELETE_WINDOW', cancel)
        elif any(len(cost.candidates(species)) < count for species, count in groups):
            self._page_tip('任务要求的宠物不足，请准备好后再来。', cancel)
            self.ui_window.protocol('WM_DELETE_WINDOW', cancel)
        else:
            paint()
        return False
