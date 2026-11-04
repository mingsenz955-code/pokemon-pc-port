"""Native Windows migration verification build. This is not the complete game."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import tkinter as tk
from collections import OrderedDict
from game_overlay import GameOverlay
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk

from original_data import OriginalData


def data_root():
    home = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
    override = os.environ.get('POCKET_NATIVE_DATA')
    if override:
        candidate = Path(override)
        if (candidate/'tables.json').exists():
            return candidate
    packaged = home/'data'
    if (packaged/'tables.json').exists():
        return packaged
    # The X 2.10.9 stage is the default development data.  The clean 1.20.4
    # baseline remains available through POCKET_NATIVE_DATA=original-1.20.4.
    x_data = home/'x-data'
    if (x_data/'tables.json').exists():
        return x_data
    return home/'original-1.20.4'


class Preview:
    SCALE = .65
    WIDTH, HEIGHT = 1024, 576

    def __init__(self, root, data):
        self.root, self.data = root, data
        root.title('口袋妖怪 · 原生 PC 移植验证版 0.1（完整游戏尚未完成）')
        root.configure(bg='#202b30')
        root.resizable(False, False)
        self.keys, self.face = set(), 'standdown'
        self.map_id, self.x, self.y = 101, 14*64+32, (35-16)*64
        self.dialogue, self.steps, self.step_index = None, [], 0
        self.event_name, self.event_issue = '', ''
        self.hidden, self.actor_positions, self.task_state = set(), {}, {}
        self.noclip, self.visited = False, set()
        self.last_time, self.exit_time = time.monotonic(), 0
        self.save_path = Path(os.environ.get('LOCALAPPDATA', str(Path.home())))/'PocketPCVerification'/'preview-position.json'
        top = tk.Frame(root, bg='#202b30', height=42)
        top.pack(fill='x')
        tk.Label(top, text='原版资源 · Windows 原生验证', fg='#f5d492', bg='#202b30',
                 font=('Microsoft YaHei UI', 12, 'bold')).pack(side='left', padx=14, pady=10)
        for label, command in [('地图', self.choose_map), ('剧情脚本', self.choose_event),
                               ('宠物资料', self.choose_pet), ('保存位置', self.save),
                               ('恢复位置', self.restore), ('说明', self.about)]:
            ttk.Button(top, text=label, command=command).pack(side='left', padx=3)
        self.canvas = tk.Canvas(root, width=self.WIDTH, height=self.HEIGHT,
                                bg='#152320', highlightthickness=0)
        self.canvas.pack()
        self.status = tk.StringVar()
        tk.Label(root, textvariable=self.status, anchor='w', bg='#202b30', fg='#e2e4df',
                 font=('Microsoft YaHei UI', 10), padx=12, pady=8).pack(fill='x')
        root.bind('<KeyPress>', self.key_down)
        root.bind('<KeyRelease>', lambda e: self.keys.discard(e.keysym.lower()))
        root.bind('<FocusOut>', lambda e: self.keys.clear())
        self.canvas.bind('<Button-1>', lambda e: self.interact())
        self.load_map(101, self.x, self.y)
        self.play_event('pEvent101001.json')
        self.frame = None
        self.tick()

    def key_down(self, event):
        key = event.keysym.lower()
        if key in ['space', 'return', 'e']:
            self.interact()
        elif key == 'escape':
            self.dialogue, self.steps, self.event_issue = None, [], ''
        elif key == 'm':
            self.choose_map()
        elif key == 'f5':
            self.save()
        elif key == 'f9':
            self.restore()
        elif key == 'f3':
            self.noclip = not self.noclip
        else:
            self.keys.add(key)

    def load_map(self, mid, x=None, y=None):
        self.map = self.data.load_map(mid)
        self.map_id = int(mid)
        self.background = self.map.render(self.SCALE, include_objects=not getattr(self, 'DYNAMIC_SCENERY', False))
        self.actor_positions, self.hidden = {}, set()
        self.x = x if x is not None else self.map.width*32
        self.y = y if y is not None else self.map.height*32
        self.steps, self.dialogue, self.event_issue = [], None, ''
        self.exit_time = time.monotonic()+1
        self.visited.add(self.map_id)
        row = self.data.tables['Sound'].get(self.map.info.get('bgmId'), {})
        # Audio uses the Windows multimedia API; game networking is never initialized.
        self.play_music(row)

    def play_music(self, row):
        if not hasattr(self, 'audio'):
            from game_audio import GameAudio
            self.audio = GameAudio(self.data)
        self.audio.music(row)

    def actors(self):
        result = []
        for obj in self.map.objects:
            if obj['group'] != 'spriteLayer' or not obj.get('gid'):
                continue
            oid = obj.get('name', '')
            if oid in self.hidden or obj['props'].get('state') == '0':
                continue
            sid = self.map.tile_properties(int(obj['gid'])).get('spriteId')
            if not sid:
                continue
            x, y = self.actor_positions.get(oid, (float(obj['x'])+32, float(obj['y'])))
            result.append((oid, sid, x, y))
        return result

    def play_event(self, filename):
        try:
            self.steps = self.data.event(filename)
        except (FileNotFoundError, ValueError):
            self.event_issue = '该对象尚未关联到可验证的原版剧情脚本。'
            return
        self.event_name, self.step_index, self.event_issue = filename, 0, ''
        self.next_step()

    def next_step(self):
        self.dialogue = None
        # Stop at any unimplemented command instead of inventing rewards or battle results.
        for _ in range(150):
            if self.step_index >= len(self.steps):
                self.steps = []
                return
            step = self.steps[self.step_index]
            self.step_index += 1
            kind, params = step.get('type'), step.get('parameters', {})
            if kind in ['talk', 'aside', 'airtalk']:
                self.dialogue = step.get('text', '')
                return
            if kind == 'end':
                self.steps = []
                return
            if kind in ['toplace', 'face', 'toface']:
                for p in params if isinstance(params, list) else [params]:
                    if kind == 'toplace' and 'x' in p and 'y' in p:
                        pos = (float(p['x'])*64+32, (self.map.height-float(p['y']))*64)
                        if p.get('spritetype') == 1:
                            self.x, self.y = pos
                        else:
                            self.actor_positions[str(p.get('spriteid'))] = pos
                continue
            if kind == 'spritevisible':
                for p in params if isinstance(params, list) else [params]:
                    oid = str(p.get('spriteid'))
                    if p.get('visible'):
                        self.hidden.discard(oid)
                    else:
                        self.hidden.add(oid)
                continue
            if kind == 'submittask':
                self.task_state[str(params.get('mtask', params.get('btask')))] = 'submitted-in-preview'
                continue
            self.event_issue = f'脚本验证停在原指令「{kind}」：此功能尚未移植，未跳过或伪造结果。'
            self.steps = []
            return
        self.event_issue = '脚本步数超过本次验证上限，已停止。'
        self.steps = []

    def interact(self):
        if self.dialogue is not None:
            self.next_step()
            return
        actors = sorted(self.actors(), key=lambda a: (a[2]-self.x)**2+(a[3]-self.y)**2)
        if actors and (actors[0][2]-self.x)**2+(actors[0][3]-self.y)**2 < 150**2:
            self.play_event('pEventTalk'+actors[0][0]+'.json')

    def exit_spawn(self, game_map, obj):
        """Return a walkable point just inside the destination map.

        The TMX ``face`` field points from the exit into the map it leaves;
        a player arriving through it must stand on the opposite side of the
        rectangle.  The old code offset the centre *toward* ``face`` and could
        place the player at negative coordinates on top-edge exits.
        """
        x = float(obj.get('x', 0))+float(obj.get('width', 64))/2
        y = float(obj.get('y', 0))+float(obj.get('height', 64))/2
        w = float(obj.get('width', 64))
        h = float(obj.get('height', 64))
        face = str(obj.get('props', {}).get('face', '2'))
        if face == '1':       # exit points up: arrive below it
            y = float(obj.get('y', 0))+h+32
        elif face == '2':     # exit points down: arrive above it
            y = float(obj.get('y', 0))-32
        elif face == '3':     # exit points left: arrive on its right
            x = float(obj.get('x', 0))+w+32
        elif face == '4':     # exit points right: arrive on its left
            x = float(obj.get('x', 0))-32
        x = max(32.0, min(x, game_map.width*64-32.0))
        y = max(32.0, min(y, game_map.height*64-32.0))
        if not game_map.blocked(x, y):
            return x, y
        # Exits are sometimes drawn over a blocked decorative tile.  Pick the
        # nearest passable tile centre rather than spawning inside a wall.
        tx, ty = int(x//64), int(y//64)
        for radius in range(1, 8):
            candidates = []
            for dx in range(-radius, radius+1):
                for dy in range(-radius, radius+1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    nx, ny = tx+dx, ty+dy
                    if not (0 <= nx < game_map.width and 0 <= ny < game_map.height):
                        continue
                    px, py = nx*64+32, ny*64+32
                    if not game_map.blocked(px, py):
                        candidates.append((abs(px-x)+abs(py-y), px, py))
            if candidates:
                return min(candidates)[1:]
        return x, y

    def try_exit(self):
        if time.monotonic() < self.exit_time:
            return
        for obj in self.map.objects:
            p = obj['props']
            if obj['group'] != 'spriteLayer' or 'toExit' not in p:
                continue
            x, y = float(obj.get('x', 0)), float(obj.get('y', 0))
            w, h = float(obj.get('width', 64)), float(obj.get('height', 64))
            if not (x <= self.x < x+w and y <= self.y < y+h):
                continue
            target = p['toExit']
            for mid, row in self.data.tables['VillageMap'].items():
                if target not in row['exitIds'].split(','):
                    continue
                dest = self.data.load_map(mid)
                candidates = [o for o in dest.objects if o.get('name') == target and 'toExit' in o['props']]
                if candidates:
                    tx, ty = self.exit_spawn(dest, candidates[0])
                    self.load_map(mid, tx, ty)
                else:
                    self.load_map(mid)
                return

    def actor_animation(self, oid, sid):
        return 'closed' if str(sid) == '30001' else 'standdown'

    def player_image(self, face):
        return self.data.village_sprite(getattr(self, 'player_sprite', '10001'), face)

    def scene_sprite(self, sid, animation):
        return self.data.village_sprite(sid, animation)

    def render_actor_overlay(self, frame, oid, sid, sx, sy, sprite, anchor):
        pass

    def render_world_overlay(self, frame, camx, camy):
        pass

    def make_frame(self):
        camx, camy = self.camera_origin()
        frame = Image.new('RGBA', (self.WIDTH, self.HEIGHT), '#1d2927')
        crop = self.background.crop((int(camx), int(camy), int(camx)+self.WIDTH, int(camy)+self.HEIGHT))
        frame.alpha_composite(crop)
        self.render_world_overlay(frame, camx, camy)
        entities = [(sid, x, y, self.actor_animation(oid, sid), None, oid) for oid, sid, x, y in self.actors()]
        if getattr(self, 'DYNAMIC_SCENERY', False):
            entities.extend((None, x, y, '', image, None) for x, y, image in self.map.scenery())
        if getattr(self, 'player_visible', True):
            entities.append((None, self.x, self.y, self.face, None, None))
        for sid, x, y, face, scenery_image, oid in sorted(entities, key=lambda a: a[2]):
            sx, sy = x*self.SCALE-camx, y*self.SCALE-camy
            sprite = scenery_image if scenery_image is not None else (
                self.player_image(face) if sid is None else self.scene_sprite(sid, face))
            if sprite is None:
                continue
            size = (max(1, round(sprite.width*self.SCALE)), max(1, round(sprite.height*self.SCALE)))
            anchor = sprite.info.get('origin', (sprite.width/2, sprite.height))
            left, top = sx-anchor[0]*self.SCALE, sy-anchor[1]*self.SCALE
            if left >= self.WIDTH or top >= self.HEIGHT or left+size[0] <= 0 or top+size[1] <= 0:
                continue
            # Static scenery and repeated poses retain image identity. Resize
            # each once instead of resampling every building on every frame.
            if not hasattr(self, '_scaled_sprites'):
                self._scaled_sprites = OrderedDict()
            cache_key = (id(sprite), size)
            cached = self._scaled_sprites.get(cache_key)
            if cached is not None and cached[0] is sprite:
                self._scaled_sprites.move_to_end(cache_key)
                sprite = cached[1]
            else:
                source = sprite
                sprite = sprite.resize(size, Image.Resampling.LANCZOS)
                self._scaled_sprites[cache_key] = (source, sprite)
                while len(self._scaled_sprites) > 512:
                    self._scaled_sprites.popitem(last=False)
            frame.alpha_composite(sprite, (round(sx-anchor[0]*self.SCALE), round(sy-anchor[1]*self.SCALE)))
            if oid is not None:
                self.render_actor_overlay(frame, oid, sid, sx, sy, sprite, anchor)
        draw = ImageDraw.Draw(frame)
        font_path = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts/msyh.ttc'
        font = ImageFont.truetype(str(font_path), 18)
        if getattr(self, 'show_map_label', True):
            draw.rounded_rectangle((14, 12, 340, 49), radius=10, fill=(42, 43, 30, 220))
            draw.text((28, 18), self.map.info['name']+' · 原版地图', font=font, fill='#fff3d0')
        if self.dialogue is not None:
            name, sep, text = self.dialogue.partition(':')
            if not sep:
                name, text = '', self.dialogue
            portrait = next((r.get('icon') for r in self.data.tables['Npc'].values() if r['name'] == name), None)
            if portrait:
                im = self.data.image('res/UI/HeadIcon/'+portrait)
                im.thumbnail((220, 335), Image.Resampling.LANCZOS)
                frame.alpha_composite(im, (self.WIDTH-im.width, self.HEIGHT-im.height))
            draw.rounded_rectangle((38, 431, 810, 565), radius=12, fill='#f1e6cc', outline='#805439', width=3)
            draw.rounded_rectangle((54, 401, 228, 439), radius=8, fill='#f1e6cc', outline='#805439', width=2)
            draw.text((70, 408), name, font=font, fill='#5f4029')
            text = __import__('re').sub(r'#[0-9]', '', text)
            lines, line = [], ''
            for ch in text:
                if draw.textlength(line+ch, font=font) > 700 or ch == '\n':
                    lines.append(line)
                    line = '' if ch == '\n' else ch
                else:
                    line += ch
            lines.append(line)
            for i, line in enumerate(lines[:3]):
                draw.text((60, 450+i*27), line, font=font, fill='#4c3524')
            draw.text((655, 533), '空格 / 单击继续', font=ImageFont.truetype(str(font_path), 14), fill='#7a614a')
        return frame

    def follow_focus(self):
        return self.x, self.y

    def camera_origin(self, focus=None):
        focus = focus if focus is not None else (getattr(self, 'camera_focus', None) or self.follow_focus())
        return (max(0, min(focus[0]*self.SCALE-self.WIDTH/2, self.background.width-self.WIDTH)),
                max(0, min(focus[1]*self.SCALE-self.HEIGHT/2, self.background.height-self.HEIGHT)))

    def tick(self):
        frame_started = getattr(self, "_frame_started", time.perf_counter())
        now = time.monotonic()
        dt, self.last_time = min(.06, now-self.last_time), now
        if self.dialogue is None and not self.steps:
            dx = int(bool(self.keys & {'right', 'd'}))-int(bool(self.keys & {'left', 'a'}))
            dy = int(bool(self.keys & {'down', 's'}))-int(bool(self.keys & {'up', 'w'}))
            if dx or dy:
                speed = self.movement_speed()*dt/(1.4142 if dx and dy else 1)
                if dx:
                    self.face = 'standleft' if dx < 0 else 'standright'
                elif dy:
                    self.face = 'standup' if dy < 0 else 'standdown'
                nx, ny = self.x+dx*speed, self.y+dy*speed
                self.move_to(nx, self.y)
                self.move_to(self.x, ny)
                self.try_exit()
        self.frame = self.make_frame()
        if hasattr(self, 'viewport'):
            self.viewport.present(self.frame)
        else:
            self.tk_image = ImageTk.PhotoImage(self.frame)
        if not hasattr(self, 'canvas_image'):
            self.canvas_image = self.canvas.create_image(0, 0, anchor='nw', image=self.tk_image)
        else:
            self.canvas.itemconfig(self.canvas_image, image=self.tk_image)
        self.status.set(self.event_issue or ('WASD/方向键移动 · 空格/E对话 · M地图 · F5保存 · Esc结束脚本'
                                            + (' · F3穿墙核验开启' if self.noclip else '')
                                            + '   |   开发验证版：战斗、养成、任务流程尚未完成'))
        delay = max(3, round(1000/getattr(self, 'TARGET_FPS', 25)-(time.perf_counter()-frame_started)*1000))
        self.root.after(delay, self.tick)

    def move_to(self, x, y):
        if self.noclip or not self.map.blocked(x, y):
            self.x = max(0, min(x, self.map.width*self.map.tw-1))
            self.y = max(0, min(y, self.map.height*self.map.th-1))

    def movement_speed(self):
        return 320.0

    def choose(self, title, rows, callback):
        win = GameOverlay(self)
        win.title(title)
        win.geometry('600x600')
        query = tk.StringVar()
        entry = ttk.Entry(win, textvariable=query)
        entry.pack(fill='x', padx=12, pady=12)
        box = tk.Listbox(win, font=('Microsoft YaHei UI', 10))
        box.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        current = []
        def update(*_):
            current[:] = [(k, text) for k, text in rows if query.get().lower() in text.lower()]
            box.delete(0, 'end')
            for _, text in current:
                box.insert('end', text)
        def select(*_):
            if box.curselection():
                k = current[box.curselection()[0]][0]
                win.destroy()
                callback(k)
        query.trace_add('write', update)
        box.bind('<Double-Button-1>', select)
        box.bind('<Return>', select)
        ttk.Button(win, text='打开选中项', command=select).pack(pady=(0, 12))
        update()
        entry.focus_set()

    def choose_map(self):
        rows = [(k, f'{k}   {r["name"]}') for k, r in sorted(self.data.tables['VillageMap'].items(), key=lambda x: int(x[0]))]
        self.choose('原版地图核验（不代表主线进度已解锁）', rows, self.load_map)

    def choose_event(self):
        rows = []
        for p in sorted((self.data.root/'events').glob('*.json')):
            steps = self.data.event(p.name)
            text = next((s.get('text', '') for s in steps if s.get('type') == 'talk'), '')
            rows.append((p.name, p.stem+'  '+text[:45]))
        self.choose('原版脚本核验（仅执行已实现指令）', rows, self.play_event)

    def choose_pet(self):
        rows = [(k, f'{k}   {r["name"]}   原版上限 {r["maxLevel"]}级')
                for k, r in sorted(self.data.tables['Pet'].items(), key=lambda x: int(x[0]))]
        def show(k):
            r = self.data.tables['Pet'][k]
            win = GameOverlay(self)
            win.title(r['name']+' · 原始配置')
            text = tk.Text(win, font=('Microsoft YaHei UI', 11), wrap='word', width=68, height=24)
            text.pack(fill='both', expand=True)
            content = f'{r["name"]}\n\n{r["des"]}\n\n原版等级上限：{r["maxLevel"]}\n基础属性：{r["attributeBase"]}\n\n技能：\n'
            for sid in r['skillIds'].split(','):
                s = self.data.tables['Skill'].get(sid)
                if s:
                    content += s['name']+'：'+s.get('des', '')+'\n'
            content += '\n原始字段：\n'+json.dumps(r, ensure_ascii=False, indent=2)
            text.insert('1.0', content)
            text.config(state='disabled')
        self.choose('原版宠物资料（315条配置，不是已实现的养成系统）', rows, show)

    def save(self):
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {'format': 'preview-only-v1', 'map': self.map_id, 'x': self.x, 'y': self.y}
        temp = self.save_path.with_suffix('.tmp')
        temp.write_text(json.dumps(payload), encoding='utf-8')
        os.replace(temp, self.save_path)
        self.event_issue = '已保存验证程序位置；与原安卓游戏存档分开。'

    def restore(self):
        if not self.save_path.exists():
            self.event_issue = '尚未保存验证程序的位置。'
            return
        try:
            p = json.loads(self.save_path.read_text(encoding='utf-8'))
            self.load_map(p['map'], float(p['x']), float(p['y']))
        except (ValueError, KeyError, OSError) as e:
            messagebox.showerror('无法读取验证位置', str(e))

    def about(self):
        messagebox.showinfo('当前范围', '这是原生 Windows 移植验证程序，不是完整游戏。\n\n'
            '使用已核验的 1.20.4 原版地图、图片、骨骼数据与剧情文本。\n'
            '已实现：原图渲染、静态骨骼姿态、地图移动与部分出口、开场对话、原数据浏览、位置保存。\n'
            '未完成：完整事件状态机、战斗与捕捉、养成、任务条件、道馆、经济系统和动画一致性。\n'
            '地图与数据入口用于逐项核验，不代表游戏系统已经复刻。')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--screenshot', type=Path)
    args = parser.parse_args()
    root = tk.Tk()
    app = Preview(root, OriginalData(data_root()))
    if args.screenshot:
        app.frame.convert('RGB').save(args.screenshot)
    if args.smoke_test:
        root.after(1200, root.destroy)
    root.mainloop()


if __name__ == '__main__':
    main()
