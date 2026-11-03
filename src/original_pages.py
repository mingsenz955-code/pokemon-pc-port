"""Original CSB list items at authored dimensions, with clipped input/rendering.

Evidence: ShopUILayer::getItemLayout 0x3b533c; IllustratedUILayer::
itemScrollViewInit 0x36e29c; ContinuousLoginUILayer::itemListViewInit 0x3622fc.
No screenshot backgrounds or hand-drawn substitutes for the recovered cards.
"""
from __future__ import annotations

import math
import re
import time
from collections import OrderedDict
from PIL import Image, ImageTk, ImageDraw
from event_runtime import Request
from game_state import numbers
from achievements import Achievements
from continuous_login import ContinuousLogin
from pet_pages import PetPages
from hatch_pages import HatchPages
from service_pages import ServicePages


def intersect(a, b):
    result = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
    return result if result[0] < result[2] and result[1] < result[3] else None


class Page:
    """Composite prefabs without losing their independent buttons on hover."""
    def __init__(self, app, name, **args):
        self.app = app
        self.specs = []
        self.particles = []
        self.animated_pets = []
        self._pet_pose_cache = OrderedDict()
        self.hits, self.buttons, self.rects, self.actions = {}, {}, {}, {}
        self.layer = self.add(name, (0, 0), **args)

    def add(self, name, at, prefix='', clip=None, actions=None, size=None, **args):
        ui = self.app.cocos_ui
        if size is None:
            size = tuple(max(1, round(v)) for v in ui.layout(name)['tree']['size'])
        art = ui.render(name, size, **args)
        for resource, (x, y), scale, alpha in getattr(ui, 'particles', []):
            self.particles.append((resource, (x+at[0], y+at[1]), scale, alpha, clip))
        for source, destination in ((ui.rects, self.rects), (ui.hits, self.hits),
                                    (ui.buttons, self.buttons)):
            for key, rect in source.items():
                # Keep one key per node; full paths remain available for nested
                # repeated CSB nodes and callbacks resolved by their last name.
                if '/' not in key:
                    continue
                shifted = tuple(v+at[i % 2] for i, v in enumerate(rect))
                clipped = intersect(shifted, clip) if clip else shifted
                if clipped:
                    destination[prefix+key] = clipped
        if actions:
            for suffix, callback in actions.items():
                for key in self.hits:
                    if key.startswith(prefix) and key.rsplit('/', 1)[-1] == suffix:
                        self.actions[key] = callback
        self.specs.append((name, size, args, at, prefix, clip))
        if hasattr(self, 'layer'):
            if clip:
                bounds = intersect((at[0], at[1], at[0]+art.width, at[1]+art.height), clip)
                if bounds:
                    x, y, r, b = map(round, bounds)
                    self.layer.alpha_composite(art.crop((x-round(at[0]), y-round(at[1]),
                                                       r-round(at[0]), b-round(at[1]))), (x, y))
            else:
                self.layer.alpha_composite(art, tuple(round(v) for v in at))
        return art

    def hit(self, key, rect, callback, clip=None):
        rect = intersect(rect, clip) if clip else rect
        if rect:
            self.hits[key], self.actions[key] = rect, callback

    def feedback(self, active):
        result = getattr(self, 'display_frame', self.layer).copy()
        if not active or active not in self.buttons:
            return result
        for name, size, args, at, prefix, clip in reversed(self.specs):
            if not active.startswith(prefix):
                continue
            local = active[len(prefix):]
            if not local.startswith(self.app.cocos_ui.layout(name)['tree']['name']+'/'):
                continue
            art = self.app.cocos_ui.render(name, size, **args, pressed={local: True})
            rect = self.buttons[active]
            x, y, r, b = map(round, rect)
            result.paste(art.crop((x-round(at[0]), y-round(at[1]),
                                  r-round(at[0]), b-round(at[1]))), (x, y))
            break
        return result

    def publish(self):
        app = self.app
        app.original_page = self
        self.effect_start = time.monotonic()
        app.ui_base_layer = self.pet_frame(self.frame_at(0) if hasattr(self, 'frame_at') else self.layer.copy(), 0)
        self.display_frame = app.ui_base_layer
        app.ui_hits, app.ui_buttons, app.ui_rects = self.hits, self.buttons, self.rects
        if hasattr(app, '_decorate_ui_tutorial'):
            app.ui_base_layer = app._decorate_ui_tutorial(app.ui_base_layer)
        # Public short rects support existing host callers/tests, while callbacks
        # and hit testing retain unique full paths for each repeated card.
        for key, rect in list(self.rects.items()):
            app.ui_rects.setdefault(key.rsplit('/', 1)[-1], rect)
        app.ui_button_text = {}
        app.ui_actions = self.actions
        label = getattr(app, 'ui_art_label', None)
        if label is not None and label.winfo_exists():
            label.set_layer(app.ui_base_layer)
        if (self.particles or self.animated_pets) and getattr(app, 'ui_window', None) is not None:
            job = getattr(app, 'ui_effect_job', None)
            if job:
                app.ui_window.after_cancel(job)
            self.effect_start = time.monotonic()
            app.ui_effect_job = app.ui_window.after(40, self.animate)

    def pet_frame(self, frame, elapsed):
        if elapsed < getattr(self, 'pet_visible_after', 0):
            return frame
        for species, point, area, limit in self.animated_pets:
            duration = self.app.data.pet_clip_duration(species, 'stand')
            index = int((elapsed % duration if duration else elapsed)*30)
            key = (species, index, limit)
            cached = self._pet_pose_cache.get(key)
            if cached is None:
                art = self.app.data.pet_frame(species, 'stand', index, True, fps=30, limit=max(220, limit))
                setup = self.app.data.pet_image(species)
                if art is None or setup is None:
                    continue
                ratio = min(limit/setup.width, limit/setup.height)*setup.info.get('pixels_per_unit', 1)/art.info.get('pixels_per_unit', 1)
                origin = art.info.get('origin', (art.width/2, art.height))
                art = art.resize((max(1, round(art.width*ratio)), max(1, round(art.height*ratio))), Image.Resampling.LANCZOS)
                cached = art, (origin[0]*ratio, origin[1]*ratio)
                self._pet_pose_cache[key] = cached
                if len(self._pet_pose_cache) > 96:
                    self._pet_pose_cache.popitem(last=False)
            else:
                self._pet_pose_cache.move_to_end(key)
            art, origin = cached
            x, y = round(point[0]-origin[0]), round(point[1]-origin[1])
            box = intersect((x, y, x+art.width, y+art.height), area)
            box = intersect(box, (0, 0, frame.width, frame.height)) if box else None
            if box:
                left, top, right, bottom = map(round, box)
                frame.alpha_composite(art.crop((left-x, top-y, right-x, bottom-y)), (left, top))
        return frame

    def animate(self):
        started = time.perf_counter()
        app = self.app
        if getattr(app, 'original_page', None) is not self or not app.ui_window or not app.ui_window.winfo_exists():
            return
        from particles import draw_emitter
        age = time.monotonic()-self.effect_start
        frame = self.pet_frame(self.frame_at(age) if hasattr(self, 'frame_at') else self.layer.copy(), age)
        for resource, position, scale, alpha, clip in self.particles:
            path = app.data.assets/'res'/resource
            if path.exists():
                draw_emitter(frame, path, position, scale, time.monotonic()-self.effect_start, alpha, clip)
        self.display_frame = frame
        app.ui_base_layer = frame
        app.ui_art_label.set_layer(frame)
        delay = max(3, round(1000/60-(time.perf_counter()-started)*1000))
        app.ui_effect_job = app.ui_window.after(delay, self.animate)


class OriginalPages(PetPages, HatchPages, ServicePages):
    def _choice_page(self, message, yes, no):
        previous = self.ui_base_layer.copy()
        page = Page(self, 'SecondConfirmUI', text={'tip_Text': message})
        # Use the resource's authored text node; no host OS dialog.
        fields = {k: message for k in page.rects if k.endswith(('/tip_Text', '/info_Text'))}
        if fields:
            page = Page(self, 'SecondConfirmUI', text=fields)
        art = page.layer
        page.layer = previous
        page.layer.alpha_composite(art)
        page.actions.update({'confirm_Button': yes, 'cancel_Button': no, 'close_Button': no})
        page.publish()

    def _add_page_close(self, page, at=(742, 16)):
        # ShopUI/MysteriousShopUI do not carry a close node in their CSB,
        # although the original layer responds to the tutorial close_Button.
        # Use the original button_close.png rather than drawing a host button.
        art = self.data.image('UI/button_close.png').resize((40, 40), Image.Resampling.LANCZOS)
        page.layer.alpha_composite(art, tuple(at))
        page.hit('close_Button', (at[0], at[1], at[0]+40, at[1]+40), self.close_ui)

    def _gold_store_page(self, body, info):
        body.pack_forget()
        # The platform -1 free exp stone is a real Store row, but it belongs to
        # the pEvent101006 tutorial shop. Exposing it in the normal gold shop
        # would displace the first paid pack and make the tutorial alias point
        # at the wrong card, so include it only while that event is active.
        tutorial_shop = self.runtime.file == 'pEvent101006.json'
        goods = [(k, r) for k, r in sorted(self.data.tables['Store'].items(), key=lambda p: int(p[0]))
                 if (r['platform'] == '0' or
                     (tutorial_shop and r['platform'] == '-1' and int(r['costCount']) == 0))
                 and r['shopType'] in ('1', '2', '7')
                 and not (r['costMoneyType'] == '700001' and r['gotItemKid'] == '700001')]
        offset, selected = [0], [0]

        def free_buy(key):
            # Store key 1 is the original platform -1 / cost 0 tutorial
            # experience stone. It is a real Store row and a real grant, but
            # the repeat flag is not used to mint extra stones.
            claimed = self.state.activities.setdefault('tutorial_free_store', {})
            if claimed.get(str(key)):
                if self.ui_info:
                    self.ui_info.set('这份引导奖励已经领取过了。')
                paint()
                return
            try:
                rewards = self.state.buy_store(key)
            except (ValueError, KeyError) as error:
                self._page_tip(str(error), paint)
                return
            claimed[str(key)] = 1
            # Keep the shop page open: the original tutorial's next step
            # clicks close_Button on the shop itself, not a reward modal.
            names = '、'.join(f'{self._item_data(k)[0]}×{n}' for k, n in rewards)
            if self.ui_info:
                self.ui_info.set(f'已领取：{names}')
            paint()

        def paint():
            row = goods[selected[0]][1]
            info.set(f'商店 · {row["name"]}\n{row["des"]}')
            page = Page(self, 'ShopUI', text={'info_Text': row['des'], **self._money_text()},
                        resources=self._money_icons(), sizes={'info_Text': (335, 60)})
            area = page.rects['Layer/root_Panel/goods_ListView']
            for i, (key, row) in enumerate(goods):
                x, y = round(area[0]+i*163-offset[0]), round(area[1])
                if x+153 <= area[0] or x >= area[2]:
                    continue
                money = self.data.tables['Money'].get(row['costMoneyType'], {})
                free = int(row['costCount']) == 0
                page.add('ShopGoodsUI', (x, y), prefix=f'gold_store_{i}/', clip=area,
                    sizes={'cost_BitmapFontLabel': (64, 22)},
                    text={'name_Text': row['name'], 'cost_BitmapFontLabel': row['costCount'],
                          'count_BitmapFontLabel': f"x{row['gotCount']}" if row['gotItemKid'] != '0' else ''},
                    resources={'icon_Image': 'ItemIcon/'+row['texture'],
                               'moneyIcon_Image': 'UI/'+money.get('littleIconTexture', 'money_little_icon_gold.png')},
                    native_resources=('icon_Image',),
                    visible={'selected_Image': i == selected[0], 'free_Image': free,
                             'yuan_Image': False, 'addSend_Image': False, 'discount_Panel': False,
                             'timesLimitedSale_Image': False},
                    actions={'buy_Button': (lambda k=key: free_buy(k)) if free
                             else (lambda k=key: choose_buy(k))})
                page.hit(f'gold_store_card_{i}', (x, y, x+153, y+180), lambda n=i: select(n), area)
                if free:
                    button = next((rect for name, rect in page.hits.items()
                                   if name.startswith(f'gold_store_{i}/') and name.endswith('/buy_Button')), None)
                    if button:
                        # pEvent101006 addresses the first tutorial goods
                        # button as buy_Button_1 in the original UI tree.
                        page.hit(f'buy_Button_{i+1}', button,
                                 lambda k=key: free_buy(k), area)
            page.actions['close_Button'] = self.close_ui
            self._add_page_close(page)
            page.publish()
        def select(index):
            selected[0] = index
            paint()
        def choose_buy(key):
            row = self.data.tables['Store'][key]
            money = self.data.tables['Money'][row['costMoneyType']]['name']
            def buy():
                try:
                    rewards = self.state.buy_store(key)
                except (ValueError, KeyError) as error:
                    self._page_tip(str(error), paint)
                    return
                self.reward_overlay(rewards, back=paint, underlay=False)
            self._choice_page(f"购买{row['name']}：{row['costCount']} {money}？", buy, paint)
        def wheel(event):
            offset[0] = max(0, min(max(0, len(goods)*163-517), offset[0]+(-163 if event.delta > 0 else 163)))
            paint()
        self._page_wheel(wheel)
        paint()

    def _lottery_page(self, body, info):
        from activities import Activities
        body.pack_forget()
        def paint():
            seconds = max(0, int(self.state.activities.get('lucky_free_at', 0))-int(time.time()))
            page = Page(self, 'LuckyDrawUI', timeline_frame=60, text={
                'surplusTime_BitmapFontLabel': f'{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}',
                'price_1_BitmapFontLabel': '10', 'price_2_BitmapFontLabel': '25',
                'price_3_BitmapFontLabel': '50', 'price_3_old_BitmapFontLabel': '75',
                'cost_1_BitmapFontLabel': self.data.tables['Store']['70601']['costCount'],
                'cost_2_BitmapFontLabel': self.data.tables['Store']['70602']['costCount'],
                'cost_3_BitmapFontLabel': self.data.tables['Store']['70603']['costCount']},
                visible={'weixin_Button': False, 'yuan_Image': False, 'yuan_2_Image': False,
                         'price_1_BitmapFontLabel': False, 'price_2_BitmapFontLabel': False,
                         'draw_3_Button': False, 'draw_3_1_Button': True,
                         'free_Image': seconds == 0, 'moneyIcon_1_Image': seconds > 0,
                         'cost_1_BitmapFontLabel': seconds > 0,
                         'moneyIcon_2_Image': True, 'cost_2_BitmapFontLabel': True,
                         'moneyIcon_3_Image': True, 'cost_3_BitmapFontLabel': True})
            page.actions.update({'draw_1_Button': lambda: draw(1),
                                 'draw_2_Button': lambda: draw(2), 'draw_3_Button': lambda: draw(3),
                                 'draw_3_1_Button': lambda: draw(3), 'close_Button': self.close_ui})
            page.publish()
            # Keep the visible countdown current, but only while this exact
            # page remains open; returning from a result starts a new clock.
            def refresh():
                if self.original_page is page and self.ui_window and self.ui_window.winfo_exists():
                    paint()
            self.root.after(1000, refresh)
        def draw(kind):
            if self.state.functions.get('8', 0) != 1:
                self._page_tip('抽宠会在完成原版道馆训练剧情后开放。', paint)
                return
            try:
                now = int(time.time())
                free = kind == 1 and now >= int(self.state.activities.get('lucky_free_at', 0))
                pets = Activities(self.state).draw_pets(kind, free=free, now=now)
            except (ValueError, KeyError) as error:
                self._page_tip(str(error), paint)
                return
            if pets:
                from lottery_animation import LotteryAnimation
                self.lottery_animation = LotteryAnimation(self, pets, kind)
                self.lottery_animation.start()
        paint()

    def _treasure_page(self, body, info, par1=None):
        from treasure import TreasureHunt
        body.pack_forget()
        hunt = TreasureHunt(self.state)
        if hunt.active() is None:
            self._treasure_buy_page(info, par1)
            return
        def paint():
            current = hunt.active()
            row = self.data.tables['Treasure'].get(str(current['id'])) if current else None
            text = row['des'] if row else '当前没有藏宝图，请先获得一张藏宝图。'
            if current and current.get('revealed'):
                text += '\n宝藏已经显现，前往线索地点寻找吧。'
            page = Page(self, 'TreasureCheckUI', timeline_frame=60, text={
                'tip_Text': '', 'costTip_Text': '每次使用消耗一个放大镜',
                'haveTip_Text': f'持有数量：{self.state.count("220007")}',
                'have_BitmapFontLabel': str(self.state.count('220007'))},
                resources={'icon_Image': self._item_data('220007')[1]},
                visible={'have_BitmapFontLabel': False},
                sizes={'icon_Image': (52, 52), 'tipBg_Image': (450, 94), 'haveTip_Text': (150, 18)})
            from pet_pages import text_box
            box = next(r for k, r in page.rects.items() if k.endswith('/tipBg_Image'))
            text_box(page, (box[0]+18, box[1]+15, box[2]-18, box[3]-15), text, self.cocos_ui.font('', 16))
            page.actions.update({'use_Button': search, 'giveUp_Button': give_up, 'close_Button': self.close_ui})
            page.publish()
        def search():
            try:
                self.search_treasure()
            except (ValueError, KeyError) as error:
                self._page_tip(str(error), paint)
                return
            self.close_ui('yes')
        def give_up():
            if not hunt.active():
                self._page_tip('当前没有可放弃的藏宝图。', paint)
                return
            page = Page(self, 'SecondConfirmUI', text={'info_Text': '确定放弃当前藏宝图？'})
            page.actions.update({'confirm_Button': abandon, 'cancel_Button': paint, 'close_Button': paint})
            page.publish()
        def abandon():
            hunt.give_up()
            self._treasure_buy_page(info)
        paint()

    def _treasure_buy_page(self, info, key=None):
        from treasure import TreasureHunt
        rows = self.data.tables['Treasure']
        # Explicit original UI parameters retain their original destination.
        key = str(key) if str(key) in rows else min(rows, key=int)
        row = rows[key]
        def paint():
            currency = self.data.tables['Money'][row['moneyType']]['name']
            page = Page(self, 'TreasureBuyConfirmUI', timeline_frame=60,
                        text={'costTip_Text': f'需花费{currency}：', 'cost_BitmapFontLabel': 'x'+row['price']})
            page.actions.update({'buy_Button': buy, 'close_Button': self.close_ui})
            page.publish()
        def buy():
            try:
                TreasureHunt(self.state).buy(key)
            except ValueError as error:
                self._page_tip(str(error), paint)
                return
            back = lambda: self._treasure_page(self.ui_body, info)
            self.reward_overlay([(row['itemId'], int(row['itemCount']))], back, '藏宝图附赠道具')
        paint()

    def reward_overlay(self, items, back=None, title='获得物品', *, underlay=True):
        previous = self.ui_base_layer.copy() if underlay and back and self.ui_base_layer is not None else None
        previous_wheel = getattr(self, 'page_wheel', None)
        items = [(str(k), int(n)) for k, n in items if int(n) > 0]
        offset = [0]
        def done():
            self.reward_visible = False
            self._page_wheel(previous_wheel)
            (back or self.close_ui)()
        def paint():
            page = Page(self, 'GetItemUI', timeline_frame=60, text={'title_Text': ''},
                        sizes={'bg_Image': (336, 320)},
                        positions={'item_ListView': (-134.4237, -65), 'confirm_Button': (0, -95)})
            if previous is not None:
                art = page.layer
                page.layer = previous.copy()
                page.layer.alpha_composite(art)
            ImageDraw.Draw(page.layer).text((400, 117), '恭喜您获得了：', font=self.cocos_ui.font('', 22),
                                             fill='#693100', anchor='mm')
            area = page.rects['Layer/root_Panel/item_ListView']
            for index, (kid, count) in enumerate(items):
                x, y = round(area[0]+max(0, (area[2]-area[0]-(len(items)*132-4))/2)+index*132-offset[0]), round(area[1])
                if x+128 <= area[0] or x >= area[2]:
                    continue
                name, icon = self._item_data(kid)
                page.add('GetItemUIItemUI', (x, y), prefix=f'reward_{index}/', clip=area,
                         text={'item_name_Text': name, 'itemCount_BitmapFontLabel': f'x{count}'},
                         resources={'icon_Image': icon},
                         native_resources=('icon_Image',))
            page.actions.update({'confirm_Button': done, 'close_Button': done})
            page.publish()
            self.reward_visible = True
        def wheel(event):
            offset[0] = max(0, min(max(0, len(items)*132-264), offset[0]+(-132 if event.delta > 0 else 132)))
            paint()
        self._page_wheel(wheel)
        paint()

    def _transport_item_page(self, kid, callback, back, info):
        allowed = set(numbers(self.data.tables['FunctionItem'][kid]['parameters']))
        maps = sorted(allowed & set(int(m) for m in self.state.visited_maps))
        offset, height = [0], [328]
        def paint():
            page = Page(self, 'MapSelectUI')
            area = next(r for k, r in page.rects.items() if k.endswith('_ListView'))
            height[0] = area[3]-area[1]
            for i, mid in enumerate(maps):
                name = self.data.tables['VillageMap'][str(mid)]['name']
                x, y = round(area[0]), round(area[1]+i*48-offset[0])
                if y+48 <= area[1] or y >= area[3]:
                    continue
                page.add('MapSelectItemUI', (x, y), prefix=f'item_flight_{mid}/', clip=area,
                         text={'name_Text': name}, visible={'moneyIcon_Image': False,
                              'cost_BitmapFontLabel': False, 'selected_Image': False})
                page.hit(f'item_flight_{mid}', (x, y, area[2], y+48), lambda m=mid: callback(m), area)
            page.actions['close_Button'] = back
            page.publish()
            self._page_wheel(wheel)
        def wheel(event):
            offset[0] = max(0, min(max(0, len(maps)*48-height[0]), offset[0]+(-48 if event.delta > 0 else 48)))
            paint()
        paint()
        if not maps:
            self._page_tip('尚未到达可传送的城镇。', back)

    def _illustrated_body(self, body, info):
        body.pack_forget()
        tables = self.data.tables
        key = str(self.ui_parameters.get('species') or next(iter(self.state.encyclopedia), '100001'))
        if key not in tables['Pet']:
            self._page_tip('没有这只宠物的图鉴资料。', self.close_ui)
            return
        row = tables['Pet'][key]
        properties, scroll, limit = [False], [0], [0]

        def paint():
            page = Page(self, 'IllustratedPetInfoUI', text={
                'name_Text': row['name'], 'number_BitmapFontLabel': str(int(key) % 1000),
                'info_Text': ''},
                visible={'noName_Sprite': False, 'info_Text': not properties[0],
                         'infoTitle_1_Text': properties[0], 'infoTitle_2_Text': properties[0],
                         'property_ListView_1': properties[0], 'property_ListView_2': properties[0],
                         'check_Sprite': not properties[0], 'intro_Sprite': properties[0]})
            position = page.rects['Layer/root_Panel/info_bg_Image/petPos_Node']
            art = self.data.pet_image(key)
            if art is not None:
                art = art.copy()
                art.thumbnail((180, 175), Image.Resampling.LANCZOS)
                page.layer.alpha_composite(art, (round(position[0]-art.width/2), round(position[1]-art.height)))
            if properties[0]:
                # showPropertyPanel/showinfoPanel switch the original two
                # views. Keep their labels: locations and evolution materials,
                # not the host's unrelated 属性/技能 replacement headings.
                locations = [tables['VillageMap'].get(str(mid), {}).get('name', str(mid))
                             for mid in numbers(row.get('locations')) if mid]
                evolution = tables.get('Evolution', {}).get(key, {})
                materials = [f'{self._item_data(kid)[0]} ×{count}'
                             for kid, count in zip(numbers(evolution.get('itemIds')),
                                                   numbers(evolution.get('itemCounts')))]
                if evolution.get('level'):
                    materials.insert(0, f'等级 {evolution["level"]}')
                from pet_pages import text_box
                font = self.cocos_ui.font('', 14)
                limits = []
                for suffix, lines in (('property_ListView_1', locations or ['暂无地点']),
                                      ('property_ListView_2', materials or ['无需进化'])):
                    area = page.rects.get('Layer/root_Panel/info_bg_Image/'+suffix)
                    if area:
                        limits.append(text_box(page, area, '\n'.join(lines), font, scroll[0]))
                limit[0] = max(limits, default=0)
            else:
                from pet_pages import text_box
                area = next(r for k, r in page.rects.items() if k.endswith('/info_Text'))
                limit[0] = text_box(page, area, row.get('des', ''), self.cocos_ui.font('', 16), scroll[0])
            page.actions['check_Button'] = toggle
            page.actions['close_Button'] = self.close_ui
            page.publish()
            self._page_wheel(wheel)

        def toggle():
            properties[0] = not properties[0]
            scroll[0] = 0
            paint()
        def wheel(event):
            scroll[0] = max(0, min(limit[0], scroll[0]+(-24 if event.delta > 0 else 24)))
            paint()
        info.set(row['name'])
        paint()

    def _list_margin(self, layout, key):
        def find(node):
            if node.get('name') == key:
                return node
            return next((result for child in node.get('children', []) if (result := find(child))), None)
        return (find(self.cocos_ui.layout(layout)['tree']) or {}).get('item_margin', 0)

    def _goods_confirm_body(self, body, info):
        body.pack_forget()
        parameters = self.ui_parameters
        table = str(parameters.get('table', 'Shop'))
        key = str(parameters.get('key') or min(self.data.tables[table], key=int))
        shop_uiid = int(parameters.get('shop_uiid', 1))
        row = self.data.tables[table][key]
        money = self.data.tables['Money'].get(str(row['moneyType']), {})
        quantity = [1]
        underlay = getattr(self, 'shop_underlay', None)

        def paint():
            page = Page(self, 'BuyConfirmUI', text={
                'name_Text': row['name'], 'count_BitmapFontLabel': str(quantity[0]),
                'getItemCount_BitmapFontLabel': f'x{quantity[0]*int(row.get("gotCount", 1))}',
                'costCount_BitmapFontLabel': str(int(row['price'])*quantity[0])},
                resources={'icon_Sprite': 'ItemIcon/'+row.get('texture', ''),
                           'moneyIcon_Sprite': 'UI/'+money.get('littleIconTexture', 'money_little_icon_gold.png')},
                native_resources=('icon_Sprite',))
            if underlay:
                art = page.layer
                page.layer = underlay.copy()
                page.layer.alpha_composite(art)
            page.actions.update({'left_Button': lambda: change(-1), 'right_Button': lambda: change(1),
                                 'confirm_Button': confirm, 'cancel_Button': cancel,
                                 'buy_Button': confirm, 'close_Button': cancel})
            page.publish()

        def change(step):
            quantity[0] = max(1, min(1 if str(row.get('repeat', '1')) == '0' else 99, quantity[0]+step))
            paint()

        def confirm():
            try:
                self.state.buy(table, key, quantity[0])
            except (ValueError, KeyError, NotImplementedError) as error:
                self._page_tip(str(error), paint)
                return
            self._back_to_shop(shop_uiid)
            self.show_purchase_notice(row['name'], quantity[0]*int(row.get('gotCount', 1)))

        def cancel():
            self._back_to_shop(shop_uiid)
        info.set(row.get('des', ''))
        paint()

    def _page_tip(self, message, back):
        if self.ui_info is not None:
            self.ui_info.set(message)
        previous = self.ui_base_layer.copy()
        page = Page(self, 'TipConfirmUI', text={'tip_Text': message})
        art = page.layer
        page.layer = previous
        page.layer.alpha_composite(art)
        page.actions.update({'confirm_Button': back, 'cancel_Button': back, 'close_Button': back})
        page.publish()

    def _area_map_body(self, body, info):
        body.pack_forget()
        from area_map import region_for, parent_map, region_image
        region = [str(self.ui_parameters.get('region') or region_for(self.data, self.map_id))]
        current = parent_map(self.data, self.map_id)
        offset = [0, 0]
        maps, boxes = region_image(self, region[0])
        bounds = boxes.get(current, (maps.width/2, maps.height/2, maps.width/2, maps.height/2))
        offset[:] = [max(0, min(maps.width-672, (bounds[0]+bounds[2])/2-336)),
                     max(0, min(maps.height-353, (bounds[1]+bounds[3])/2-176))]

        def paint():
            page = Page(self, 'AreaMapUI', text={'name_Text': self.data.tables['WorldMap'][region[0]]['name']})
            area = page.rects['Layer/root_Panel/area_Panel']
            left, top, right, bottom = map(round, area)
            crop = maps.crop((round(offset[0]), round(offset[1]),
                              round(offset[0])+right-left, round(offset[1])+bottom-top))
            page.layer.alpha_composite(crop, (left, top))
            # Keep world-map and transmit controls above the clipped map.
            controls = self.cocos_ui.render('AreaMapUI', (800, 480),
                                            text={'name_Text': self.data.tables['WorldMap'][region[0]]['name']},
                                            visible={'bg_Panel': False, 'BG_Image': False})
            page.layer.alpha_composite(controls)
            page.actions.update({'close_Button': self.close_ui, 'worldMap_Button': self._world_map_page,
                                 'fly_Button': lambda: self._map_select_page(paint, info)})
            page.publish()
            self.page_drag = drag
            self._page_wheel(wheel)

        def drag(dx, dy):
            offset[0] = max(0, min(max(0, maps.width-672), offset[0]-dx))
            offset[1] = max(0, min(max(0, maps.height-353), offset[1]-dy))
            paint()

        def wheel(event):
            drag(0, 80 if event.delta > 0 else -80)
        info.set(self.map.info['name'])
        paint()

    def _world_map_page(self):
        from area_map import region_for
        hemisphere = [1 if int(region_for(self.data, self.map_id)) <= 11 else 2]

        def paint():
            name = f'WorldMap{hemisphere[0]}UI'
            # The original cloud unlock timeline is not yet modeled. Keep its
            # authored fog instead of inventing unlock flags from visited maps.
            page = Page(self, name)
            current_region = region_for(self.data, self.map_id)
            position = page.rects.get(f'Layer/root_Panel/iconPos_Node_{current_region}')
            if position:
                head = self.data.image('Map/areaMapPlayerHead.png')
                page.layer.alpha_composite(head, (round(position[0]-head.width/2),
                                                  round(position[1]-head.height/2)))
            for key, rect in list(page.rects.items()):
                short = key.rsplit('/', 1)[-1]
                if short.startswith('nameBg_') and short.endswith('_Sprite'):
                    value = short.split('_')[1]
                    page.hit('world_region_'+value, rect, lambda v=value: show(v))
            page.actions['close_Button'] = lambda: self.open_ui(Request('openui', 'area-return', 1,
                                                    {'parameters': {'uiid': 9}}))
            page.publish()
            self.page_drag = lambda dx, dy: change(-1 if dx > 0 else 1) if abs(dx) > 35 else None
            self._page_wheel(lambda e: change(-1 if e.delta > 0 else 1))

        def change(step):
            hemisphere[0] = max(1, min(2, hemisphere[0]+step))
            paint()

        def show(region):
            self.open_ui(Request('openui', 'world-region', 1, {'parameters': {'uiid': 9, 'region': region}}))
        paint()

    def _map_select_page(self, back, info):
        # isCanTransmit 0x2d8bb0 rejects type 1 (buildings), including the lab
        # and home. Roads use type 4 and must not be mistaken for interiors.
        if int(self.map.info.get('mapType', 0)) == 1:
            info.set('当前地图不能传送。')
            return
        maps = sorted({int(mid) for mid in self.state.visited_maps
                       if str(mid) in self.data.tables['VillageMap'] and
                       str(self.data.tables['VillageMap'][str(mid)].get('mapType')) == '2'})
        offset = [0]

        def paint():
            page = Page(self, 'MapSelectUI')
            area = page.rects['Layer/root_Panel/map_ListView']
            for i, mid in enumerate(maps):
                x, y = round(area[0]), round(area[1]+i*48-offset[0])
                if y+48 <= area[1] or y >= area[3]:
                    continue
                page.add('MapSelectItemUI', (x, y), prefix=f'flight_{mid}/', clip=area,
                         text={'name_Text': self.data.tables['VillageMap'][str(mid)]['name']},
                         visible={'moneyIcon_Image': False, 'cost_BitmapFontLabel': False, 'selected_Image': False})
                page.hit(f'flight_{mid}', (x, y, x+269, y+48), lambda target=mid: fly(target), area)
            page.actions['close_Button'] = back
            page.publish()
            self.page_drag = None
            self._page_wheel(wheel)

        def fly(mid):
            # Retain the existing offline visited-town transport; do not grant
            # access to unseen maps or manufacture a price from editor samples.
            if mid not in maps:
                return
            try:
                x, y = self._transport_arrival(mid)
            except ValueError as error:
                self._page_tip(str(error), paint)
                return
            self.close_ui()
            self.guide.stop()
            self.load_map(mid, x, y)
            self.runtime.notify('tomap', map=mid)
            self.drive()

        def wheel(event):
            offset[0] = max(0, min(max(0, len(maps)*48-328), offset[0]+(-48 if event.delta > 0 else 48)))
            paint()
        paint()

    def _transport_arrival(self, mid):
        """Use the original <map>01 entry, checking ground before spending.

        VillageAreaMapUiLayer::handleSelectMapUISelectedEvent 0x3c56fc
        passes selectedMap*100+1 to changeMap. Use the matching exit object,
        never an NPC with the same name or the arbitrary map centre.
        """
        world = self.data.load_map(mid)
        exits = [obj for obj in world.objects if obj.get('group') == 'spriteLayer'
                 and not obj.get('gid') and obj.get('props', {}).get('toExit')]

        def valid(x, y):
            return not world.blocked(x, y) and not any(
                float(obj.get('x', 0)) <= x < float(obj.get('x', 0))+float(obj.get('width', 64))
                and float(obj.get('y', 0)) <= y < float(obj.get('y', 0))+float(obj.get('height', 64))
                for obj in exits)

        entry = next((obj for obj in exits if str(obj.get('name')) == str(int(mid)*100+1)), None)
        origin = self.exit_spawn(world, entry) if entry else (world.width*32, world.height*32)
        if valid(*origin):
            return origin
        cells = [(x*64+32, y*64+32) for y in range(world.height) for x in range(world.width)
                 if valid(x*64+32, y*64+32)]
        if not cells:
            raise ValueError('目的地没有可安全到达的落点，未使用传送道具。')
        return min(cells, key=lambda p: (p[0]-origin[0])**2+(p[1]-origin[1])**2)

    def _bag_body(self, body, info):
        body.pack_forget()
        self._bag_page(info)

    def _bag_item_description(self, kid, row):
        description = row.get('des', '')
        if str(kid) == '270057':
            # The Item table only holds a one-line synopsis. The actual letter
            # belongs to the home story, not a consumable Item/PetItem effect.
            # Re-read that text in the existing scrollable bag details without
            # dispatching the story (which would repeat task/reward mutations).
            letter = next(entry['text'].partition(':')[2]
                          for entry in self.data.event('pEvent5807003.json')
                          if entry.get('id') == 12 and entry.get('type') == 'talk')
            description += '\n\n'+re.sub(r'#[0-9]', '', letter)
        return description

    def _bag_page(self, info, allowed_keys=None, select_item=None, back=None, select_on_click=False):
        tabs = {1: {1, 2, 3}, 2: {5}, 3: {6}, 4: {4, 7}, 5: {8}}
        kind, offset, selected = [2 if allowed_keys is not None else 1], [0], [None]
        description_scroll, description_limit, description_area = [0], [0], [None]
        rows = []
        stride = 89+self._list_margin('BagUI', 'item_ListView')

        def refresh():
            rows[:] = [(str(k), self.data.tables['Item'][str(k)], int(v))
                       for k, v in sorted(self.state.inventory.items(), key=lambda p: int(p[0]))
                       if int(v) > 0 and str(k) in self.data.tables['Item'] and
                       ((str(k) in allowed_keys) if allowed_keys is not None else
                        int(self.data.tables['Item'][str(k)]['type']) in tabs[kind[0]])]
            if selected[0] not in [r[0] for r in rows]:
                selected[0] = rows[0][0] if rows else None
            offset[0] = min(offset[0], max(0, len(rows)*stride-319))
            paint()

        def paint():
            entry = next((r for r in rows if r[0] == selected[0]), None)
            row = entry[1] if entry else {}
            description = self._bag_item_description(selected[0], row)
            info.set(description or '背包')
            visibility = {'heCheng_Button': allowed_keys is None and kind[0] == 5,
                          'use_Button': bool(entry) and (select_item is not None or
                                        int(row.get('useType', 0)) in (1, 2))}
            if allowed_keys is not None:
                visibility.update({f'tag_{i}_Button': False for i in range(1, 6)})
            page = Page(self, 'BagUI', text={'info_Text': '', **self._money_text()},
                        resources={**self._money_icons(), **{f'tag_{i}_Button':
                            'UI/tag_selected.png' if i == kind[0] else 'UI/tag_unselected.png' for i in range(1, 6)}},
                        visible=visibility, z_orders={f'tag_{i}_Button': 100 if i == kind[0] else 90 for i in range(1, 6)})
            from pet_pages import text_box
            # BagUI's root has an authored entrance timeline. Its Text node
            # bounds can be above the paper; use the actual paper interior.
            paper = next(r for k, r in page.rects.items() if k.endswith('/info_bg_Image'))
            # The recovered paper texture includes a transparent/shadow border.
            description_area[0] = (paper[0]+52, paper[1]+58, paper[2]-52, paper[3]-52)
            description_limit[0] = text_box(page, description_area[0], description,
                                            self.cocos_ui.font('', 18), description_scroll[0])
            area = page.rects['Layer/root_Panel/item_ListView']
            for i, (kid, row, count) in enumerate(rows):
                x, y = round(area[0]), round(area[1]+i*stride-offset[0])
                if y+89 <= area[1] or y >= area[3]:
                    continue
                page.add('BagListItemUI', (x, y), prefix=f'bag_{i}/', clip=area,
                         text={'itemName_Text': row['name'], 'itemCount_BitmapFontLabel': f'X{count}'},
                         resources={'icon_Image': 'ItemIcon/'+row['texture']},
                         native_resources=('icon_Image',),
                         sizes={'itemName_Text': (140, 24)}, visible={'selected_Image': kid == selected[0]})
                page.hit(f'bag_row_{i}', (x, y, x+300, y+89), lambda key=kid: choose(key), area)
                # pEvent101006 selects the tutorial item by its original
                # item id (chooseItem_230011), not by the host row index.
                page.hit(f'chooseItem_{kid}', (x, y, x+300, y+89),
                         lambda key=kid: choose(key), area)
            page.actions['close_Button'] = back or self.close_ui
            page.actions['use_Button'] = use
            page.actions['heCheng_Button'] = synthesize
            page.actions['bag_use'] = use
            page.actions['bag_synthesize'] = synthesize
            for i in range(1, 6):
                page.actions[f'tag_{i}_Button'] = lambda v=i: tab(v)
            page.publish()
            self._page_wheel(wheel)

        def choose(key):
            selected[0] = key
            description_scroll[0] = 0
            if select_on_click and select_item:
                select_item(key)
            else:
                paint()

        def tab(value):
            kind[0], offset[0], selected[0] = value, 0, None
            description_scroll[0] = 0
            refresh()

        def use():
            kid = selected[0]
            if kid is None:
                return
            if select_item:
                select_item(kid)
                return
            if kid == '210001':
                self.open_ui(Request('openui', 'open-chest', 1, {'parameters': {'uiid': 55}}))
                return
            if kid in self.data.tables.get('SkillItem', {}):
                def learn(pet):
                    skill = self.data.tables['SkillItem'][kid]['skillId']
                    self.open_skill_learn_confirm(pet.uid, str(skill), scroll=kid, back=46)
                self._select_page_pet(learn, paint, info)
                return
            if kid == '220001':
                def fly(mid):
                    try:
                        x, y = self._transport_arrival(mid)
                    except ValueError as error:
                        self._page_tip(str(error), lambda: self._transport_item_page(kid, fly, paint, info))
                        return
                    self.state.consume([kid], [1])
                    self.close_ui()
                    self.guide.stop()
                    self.load_map(mid, x, y)
                    self.runtime.notify('tomap', map=mid)
                    self.drive()
                self._transport_item_page(kid, fly, paint, info)
                return
            if kid in ('220002', '220003'):
                try:
                    self.use_perfume(kid)
                except ValueError as error:
                    self._page_tip(str(error), paint)
                    return
                refresh()
                return

            def apply(pet):
                try:
                    message = self.state.use_item(kid, pet)
                except ValueError as error:
                    self._page_tip(str(error), lambda: self._select_page_pet(apply, paint, info))
                    return
                refresh()
                info.set(message)
            self._select_page_pet(apply, paint, info)

        def synthesize():
            kid = selected[0]
            row = self.data.tables.get('DebrisItem', {}).get(kid)
            if not row:
                info.set('请选择可合成的碎片。')
                return
            try:
                with self.state.transaction():
                    self.state.consume([kid], [int(row['needCount'])])
                    self.state.grant(row['petId'], 1)
            except (ValueError, KeyError) as error:
                info.set(str(error))
                return
            refresh()
            info.set('合成成功：'+self._item_data(row['petId'])[0])

        def wheel(event):
            r = description_area[0]
            if r and r[0] <= getattr(event, 'x', -1) <= r[2] and r[1] <= getattr(event, 'y', -1) <= r[3]:
                description_scroll[0] = max(0, min(description_limit[0], description_scroll[0]+(-24 if event.delta > 0 else 24)))
            else:
                offset[0] = max(0, min(max(0, len(rows)*stride-319), offset[0]+(-44 if event.delta > 0 else 44)))
            paint()
        refresh()

    def _select_page_pet(self, callback, back, info):
        pets = list(self.state.pets)
        stride = 74+self._list_margin('PetSelectUI', 'pet_ListView')
        offset = [0]

        def paint():
            page = Page(self, 'PetSelectUI')
            area = page.rects['Layer/root_Panel/pet_ListView']
            for i, pet in enumerate(pets):
                row = self.data.tables['Pet'][pet.species]
                x, y = round(area[0]), round(area[1]+stride*i-offset[0])
                if y+74 <= area[1] or y >= area[3]:
                    continue
                stats = pet.stats(self.data.tables)
                page.add('PetSelectItemUI', (x, y), prefix=f'pet_select_{i}/', clip=area,
                         text={'name_Text': row['name'], 'lv_BitmapFontLabel': str(pet.level),
                               'hpHave_BitmapFontLabel': str(pet.hp), 'hpMax_BitmapFontLabel': str(stats[0]),
                               'enHave_BitmapFontLabel': str(pet.energy), 'enMax_BitmapFontLabel': str(stats[1]),
                               'friendly_BitmapFontLabel': str(pet.friendly)},
                         resources={'kind_Image': 'UI/'+self.data.tables['PetKindEnum'][str(row['kind'])]['iconTexture']},
                         visible={'selected_Image': False})
                page.hit(f'pet_select_{i}', (x, y, x+309, y+74), lambda p=pet: callback(p), area)
                # pEvent101006 uses the original prefab node name
                # petSelectItem_1 for the first selectable pet.
                if i == 0:
                    page.hit('petSelectItem_1', (x, y, x+309, y+74),
                             lambda p=pet: callback(p), area)
            page.actions['close_Button'] = back
            page.publish()

        def wheel(event):
            offset[0] = max(0, min(max(0, len(pets)*stride-320), offset[0]+(-74 if event.delta > 0 else 74)))
            paint()
        self._page_wheel(wheel)
        info.set('选择要使用道具的宠物。')
        paint()

    def _money_text(self):
        return {f'Layer/root_Panel/{node}_ProjectNode/Layer/root_Panel/goldCount_BitmapFontLabel':
                str(self.state.count(kid)) for node, kid in (('gold', '700001'), ('badge', '700002'))}

    def _money_icons(self):
        return {f'Layer/root_Panel/{node}_ProjectNode/Layer/root_Panel/icon_Sprite':
                f'UI/money_little_icon_{kind}.png' for node, kind in (('gold', 'gold'), ('badge', 'badge'))}

    def _item_data(self, kid):
        key = str(kid)
        for table in ('Item', 'Money', 'Pet'):
            row = self.data.tables.get(table, {}).get(key)
            if row:
                if table == 'Item':
                    icon = 'ItemIcon/'+row['texture']
                elif table == 'Money':
                    icon = 'UI/'+row.get('texture', row.get('littleIconTexture', ''))
                else:
                    icon = 'PetHead/head_'+row['filePath']+'.png'
                return row.get('name', key), icon
        return key, ''

    def _page_wheel(self, callback):
        self.page_wheel = callback
        if callback is None:
            self.ui_art_label.unbind('<MouseWheel>')
        else:
            self.ui_art_label.bind('<MouseWheel>', callback)

    def _shop_body(self, body, info, uiid):
        body.pack_forget()
        table = {1: 'Shop', 2: 'EvolutionShop', 3: 'SkillShop', 22: 'IArenaShop', 28: 'MedalShop',
                 69: 'BattleShop'}[uiid]
        layout = {1: 'ShopUI', 2: 'EvolutionShopUI', 3: 'SkillShopUI',
                  22: 'InfiniteArenaShopUI', 28: 'MedalShopUI', 69: 'BattleShopUI'}[uiid]
        clerk = {1: '1', 2: '3', 3: '4'}.get(uiid)
        if clerk and not self.ui_parameters.get('shop_return'):
            talks = self.state.activities.setdefault('shop_talks', {})
            talks[clerk] = int(talks.get(clerk, 0))+1
        goods = [(k, r) for k, r in sorted(self.data.tables[table].items(), key=lambda p: int(p[0]))
                 if str(r.get('repeat', '1')) != '0' or not self.state.shop_purchases.get(f'{table}:{k}')]
        selected, offset = [0], [0]
        if uiid == 69 and getattr(self, 'battle_shop_view', None):
            selected[0], offset[0] = self.battle_shop_view
        self.shop_uiid = uiid
        stride = 153+self._list_margin(layout, 'goods_ListView')

        def paint():
            if uiid == 69:
                self.battle_shop_view = (selected[0], offset[0])
            row = goods[selected[0]][1] if goods else {}
            description = row.get('des', '')
            info.set(f'商店 · {row.get("name", "")}\n{description}')
            page = Page(self, layout, text={'info_Text': description, **self._money_text()},
                        resources=self._money_icons(), sizes={'info_Text': (335, 60)})
            area = page.rects['Layer/root_Panel/goods_ListView']
            # The original list clones ShopGoodsUI root_Panel (153 x 233),
            # one horizontal row. GoodsItemNode belongs to BuyConfirmUI.
            for index, (key, row) in enumerate(goods):
                x, y = round(area[0]+index*stride-offset[0]), round(area[1])
                if x+153 <= area[0] or x >= area[2]:
                    continue
                money = self.data.tables['Money'].get(str(row['moneyType']), {})
                prefix = f'shop_goods_{index}/'
                page.add('ShopGoodsUI', (x, y), prefix=prefix, clip=area,
                         text={'name_Text': row['name'], 'cost_BitmapFontLabel': str(row['price']),
                               'count_BitmapFontLabel': f'x{row.get("count", 1)}'},
                         resources={'icon_Image': 'ItemIcon/'+row['texture'],
                                    'moneyIcon_Image': 'UI/'+money.get('littleIconTexture', 'money_little_icon_gold.png')},
                         native_resources=('icon_Image',),
                         visible={'selected_Image': index == selected[0], 'free_Image': False,
                                  'yuan_Image': False, 'addSend_Image': False,
                                  'discount_Panel': False, 'timesLimitedSale_Image': False},
                         actions={'buy_Button': lambda k=key: buy(k)})
                page.hit(f'shop_goods_{index}', (x, y, x+153, y+233),
                         lambda i=index: choose(i), area)
            page.actions['close_Button'] = self.close_ui
            page.actions['shop_detail'] = lambda: buy(goods[selected[0]][0]) if goods else None
            page.actions['shop_buy'] = page.actions['shop_detail']
            page.publish()

        def choose(index):
            selected[0] = index
            paint()

        def buy(key):
            if uiid == 69:
                selected[0] = next(i for i, (kid, _) in enumerate(goods) if kid == key)
                self.battle_shop_view = (selected[0], offset[0])
            self.open_ui(Request('openui', 'shop-buy', 1, {'parameters': {
                'uiid': 53, 'table': table, 'key': key, 'shop_uiid': uiid}}))

        def scroll(step):
            offset[0] = max(0, min(max(0, len(goods)*stride-512), offset[0]+step*stride))
            paint()
        self.shop_scroll = scroll
        self._page_wheel(lambda e: scroll(-1 if e.delta > 0 else 1))
        paint()

    def _shop_goods_body(self, body, info):
        # Old host-only uiid 52 links still work, but no fake enlarged card page.
        self._goods_confirm_body(body, info)

    def _login_body(self, body, info):
        body.pack_forget()
        login = ContinuousLogin(self.state)
        rewards = login.rewards()
        stride = 153+self._list_margin('ContinuousLoginUI', 'goods_ListView')
        selected = [max(0, (login.status()['day'] if login.status()['claimed_today'] else login.status()['next_day'])-1)]
        offset = [max(0, min(len(rewards)*stride-517, selected[0]*stride))]

        def paint():
            status = login.status()
            chosen = rewards[selected[0]]
            name, _ = self._item_data(chosen['rewardKid'])
            info.set(f'{chosen["des"]}{name} ×{chosen["rewardCount"]}')
            name_width = self.cocos_ui.font('', 20).getlength(name)
            page = Page(self, 'ContinuousLoginUI', timeline_frame=60, auto_text=('infoItemName_Text',),
                        positions={'infoItemCount_BitmapFontLabel': (210.0063+name_width+5, 45.9981)}, text={
                'days_BitmapFontLabel': str(status['day']), 'info_Text': chosen['des'],
                'infoItemName_Text': name, 'infoItemCount_BitmapFontLabel': f'x{chosen["rewardCount"]}'})
            area = page.rects['Layer/root_Panel/goods_ListView']
            for i, row in enumerate(rewards):
                x, y = round(area[0]+i*stride-offset[0]), round(area[1])
                if x+153 <= area[0] or x >= area[2]:
                    continue
                name, icon = self._item_data(row['rewardKid'])
                # The reward table owns money/pet textures as well as item ones.
                if row.get('texture'):
                    icon = ('UI/' if str(row['rewardKid']) in self.data.tables['Money'] else 'ItemIcon/')+row['texture']
                received = i+1 <= status['day']
                ready = i+1 == status['next_day'] and status['can_claim']
                page.add('ContinuousLoginItemUI', (x, y), prefix=f'login_{i}/', clip=area,
                         text={'day_BitmapFontLabel': str(i+1), 'name_Text': name,
                               'count_BitmapFontLabel': f'x{row["rewardCount"]}',
                               'get_Button': ''},
                         resources={'icon_Image': icon}, native_resources=('icon_Image',),
                         visible={'selected_Image': selected[0] == i, 'receive_Image': ready,
                                  'received_Image': received, 'wait_Image': False,
                                  'receive_Particle': ready, 'Particle_1': ready},
                         actions={'get_Button': lambda index=i: claim(index)})
                if not received and not ready:
                    caption = '明日可领' if i+1 == status['next_day'] else f'第{i+1}天开放'
                    caption_layer = Image.new('RGBA', page.layer.size)
                    ImageDraw.Draw(caption_layer).text((x+76.439, y+216.657),
                         caption, font=self.cocos_ui.font('', 16), fill='#693100', anchor='mm')
                    left, top, right, bottom = map(round, area)
                    page.layer.alpha_composite(caption_layer.crop((left, top, right, bottom)), (left, top))
                page.hit(f'login_card_{i}', (x, y, x+153, y+240), lambda index=i: choose(index), area)
            page.actions['close_Button'] = self.close_ui
            page.actions['get_Button'] = lambda: claim(selected[0])
            page.publish()

        def choose(index):
            selected[0] = index
            paint()

        def claim(index):
            status = login.status()
            if index+1 <= status['day']:
                self._page_tip('这一天的登录奖励已经领取。', paint)
                return
            if status['claimed_today']:
                self._page_tip('今天已经领取，下一份登录奖励明日开放。', paint)
                return
            if index+1 != status['next_day']:
                self._page_tip('请领取当天的登录奖励。', paint)
                return
            try:
                result = login.claim()
            except ValueError as error:
                self._page_tip(str(error), paint)
                return
            paint()
            info.set(f'领取成功：{self._item_data(result["reward"])[0]} ×{result["count"]}')
            self.reward_overlay([(result['reward'], result['count'])], paint)

        def wheel(event):
            offset[0] = max(0, min(max(0, stride*len(rewards)-517), offset[0]+(-stride if event.delta > 0 else stride)))
            paint()
        self._page_wheel(wheel)
        paint()

    def _illustrated_overview_body(self, body, info):
        body.pack_forget()
        kind, offset = [1], [0]
        species = []

        def paint():
            page = Page(self, 'IllustratedUI', text={
                'findedCount_BitmapFontLabel': str(len(self.state.encyclopedia)),
                'progress_BitmapFontLabel': f'{sum(k in self.state.encyclopedia for k in species)}/{len(species)}'},
                resources={f'tag_{i}_Button': 'UI/tag_selected.png' if i == kind[0]
                           else 'UI/tag_unselected.png' for i in range(1, 6)})
            area = page.rects['Layer/root_Panel/item_ScrollView']
            # Native code divides the item index by 5: five 115 x 113 cards.
            for index, key in enumerate(species):
                column, line = index % 5, index // 5
                x, y = round(area[0]+column*126), round(area[1]+line*119-offset[0])
                if y+113 <= area[1] or y >= area[3]:
                    continue
                row = self.data.tables['Pet'][key]
                owned = key in self.state.encyclopedia
                seen = owned or key in getattr(self.state, 'seen_species', [])
                visible = {'noName_Image': not seen, 'itemName_Text': seen,
                           'star_Panel': owned, 'star_black_Panel': not owned,
                           'none_Image': not seen}
                for i in range(1, 6):
                    visible[f'star_Image_{i}'] = i <= int(row['starLevel'])
                icon = 'PetHead/head_'+row['filePath']+'.png' if seen else 'UI/image_evolution_what.png'
                page.add('IllustratedItemUI', (x, y), prefix=f'illustrated_{index}/', clip=area,
                         text={'itemName_Text': row['name'] if seen else '',
                               'id_BitmapFontLabel': str(int(key) % 1000)},
                         resources={'head_Image': icon}, visible=visible)
                page.hit(f'illustrated_card_{index}', (x, y, x+115, y+113),
                         lambda k=key: show(k), area)
            for i in range(1, 6):
                page.actions[f'tag_{i}_Button'] = lambda value=i: tab(value)
            page.actions['close_Button'] = self.close_ui
            page.publish()

        def show(key):
            if key not in self.state.encyclopedia and key not in getattr(self.state, 'seen_species', []):
                info.set('还没有发现这只宠物。')
                return
            self.open_ui(Request('openui', 'illustrated-pet', 1, {'parameters': {'uiid': 8, 'species': key}}))

        def tab(value):
            kind[0], offset[0] = value, 0
            species[:] = sorted((k for k, r in self.data.tables['Pet'].items()
                                 if str(r.get('kind')) == str(value) and str(r.get('open', '1')) == '1'), key=int)
            info.set(self.data.tables['PetKindEnum'].get(str(value), {}).get('name', '图鉴'))
            paint()

        def wheel(event):
            offset[0] = max(0, min(max(0, math.ceil(len(species)/5)*119-328),
                                  offset[0]+(-119 if event.delta > 0 else 119)))
            paint()
        self._page_wheel(wheel)
        tab(1)

    def _achievement_body(self, body, info):
        body.pack_forget()
        api = Achievements(self.state)
        offset, selected = [0], [None]

        def entries():
            groups = self.data.tables.get('MainAchievement', {})
            result = []
            for _, group in sorted(groups.items(), key=lambda p: int(p[0])):
                ids = [str(k) for k in numbers(group['achievementList']) if str(k) in api.rows]
                if not ids:
                    continue
                # Show the first unclaimed tier; completed families keep their
                # final card, rather than showing every tier as separate rows.
                key = next((k for k in ids if k not in api.claimed()), ids[-1])
                result.append((api.entry(key), ids, ids.index(key)))
            return result

        def paint():
            rows = entries()
            page = Page(self, 'AchievementUI', text={'score_BitmapFontLabel': str(api.score()), 'tips_Text': ''})
            area = page.rects['Layer/root_Panel/item_ScrollView']
            for index, (entry, family, tier) in enumerate(rows):
                x, y = round(area[0]), round(area[1]+index*164-offset[0])
                if y+164 <= area[1] or y >= area[3]:
                    continue
                current = entry['current']
                ready, claimed = entry['status'] == 'ready', entry['status'] == 'claimed'
                fraction = min(1, (current or 0)/max(1, entry['target']))
                progress = f'{min(current, entry["target"])}/{entry["target"]}' if current is not None else '—'
                visible = {'receive_Image': ready, 'received_Image': claimed,
                           'wait_Image': not ready and not claimed, 'one_star_Panel': len(family) == 1,
                           'three_star_Panel': len(family) > 1}
                for i in range(1, 4):
                    visible[f'star_{i}_Image'] = i <= tier+(1 if claimed else 0)
                visible['star_Image'] = claimed
                prefix = f'achievement_{index}/'
                page.add('AchievementItemUI', (x, y), prefix=prefix, clip=area, size=(655, 164),
                         canvas_size=(655, 164),
                         positions={'root_Panel': (0, 54.6)},
                         text={'name_Text': entry['name'], 'info_Text': entry['des'],
                               'progress_BitmapFontLabel': progress, 'score_BitmapFontLabel': str(entry['score'])},
                         auto_text=('info_Text', 'name_Text'),
                         percentages={'progress_LoadingBar': fraction}, visible=visible,
                         actions={'receive_Button': lambda k=entry['id']: claim(k)})
                # RewardItemUI belongs inside the original reward_ListView.
                local = self.cocos_ui.rects.get('reward_ListView')
                if local:
                    reward_clip = intersect(area, (x+local[0], y+local[1], x+local[2], y+local[3]))
                    if not reward_clip:
                        continue
                    for j, (kid, count) in enumerate(zip(numbers(entry['row'].get('rewardIds')),
                                                          numbers(entry['row'].get('rewardCounts')))):
                        _, icon = self._item_data(kid)
                        rx, ry = x+local[0]+j*160, y+local[1]
                        page.add('RewardItemUI', (round(rx), round(ry)), prefix=prefix+f'reward_{j}/',
                                 clip=reward_clip,
                                 text={'count_BitmapFontLabel': f'x{count}'},
                                 resources={'icon_Image': icon}, sizes={'icon_Image': (58, 58)})
                page.hit(f'achievement_card_{index}', (x, y, x+655, y+164),
                         lambda k=entry['id']: select(k), area)
            page.actions['close_Button'] = self.close_ui
            page.actions['achievement_receive'] = lambda: claim(selected[0]) if selected[0] else None
            page.publish()

        def select(key):
            selected[0] = key
            entry = api.entry(key)
            info.set(f'{entry["name"]}：{entry["des"]}')

        def claim(key):
            try:
                result = api.claim(key)
            except (ValueError, KeyError) as error:
                self._page_tip(str(error), paint)
                return
            paint()
            info.set('奖励已领取。')
            self.reward_overlay(result['rewards'], paint)

        def wheel(event):
            offset[0] = max(0, min(max(0, len(entries())*164-328), offset[0]+(-82 if event.delta > 0 else 82)))
            paint()
        self._page_wheel(wheel)
        info.set('成就')
        paint()
