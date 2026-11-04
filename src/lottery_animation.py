"""Original LuckyDrawUILayer drawPet/movement/frame-event presentation chain."""
import math
import time
from threading import Thread
from collections import OrderedDict
from PIL import Image


class LotteryAnimation:
    FPS = 60
    LIGHT_SECONDS = 1.5
    WAIT_SECONDS = 1.2
    SCALE_SECONDS = 1.0

    def __init__(self, app, pets, kind, back='lottery'):
        self.app, self.pets, self.kind, self.back = app, list(pets), int(kind), back
        self.index = 0
        self.closed = False
        self.ready = False
        self.played_events = set()
        self._pet_frames = OrderedDict()
        self.moves = {m['name']: m for m in app.data.armature_source('niudanji')[1]['animation_data'][0]['mov_data']}
        self.background = app.cocos_ui.render('LuckyDrawEffectUI', (800, 480))
        self.first_clips = ['Animation1', 'Animation2', f'Animation3_{kind}',
                            'Animation4_1' if kind == 1 else 'Animation4_2']
        app.audio.pause_music()
        self.begin_pet(first=True)

    def begin_pet(self, first=False):
        from original_pages import Page
        self.started = time.monotonic()
        self.ready = False
        self.played_events.clear()
        self.clips = self.first_clips if first else ['Animation4_2']
        self.schedule, self.events = [], []
        cursor = 0
        for clip in self.clips:
            row = self.moves[clip]
            self.schedule.append((cursor, clip, int(row['dr'])))
            for bone in row['mov_bone_data']:
                for frame in bone['frame_data']:
                    if frame.get('evt'):
                        self.events.append(((cursor+frame['fi'])/self.FPS, frame['evt']))
            cursor += int(row['dr'])
        self.reveal_at = next(when for when, event in self.events if event == 'chouchong')
        self.info_at = self.reveal_at+self.LIGHT_SECONDS+self.WAIT_SECONDS+self.SCALE_SECONDS
        self.page = Page(self.app, 'LuckyDrawEffectUI')
        self.page.publish()
        self._warm_pet(self.pets[self.index], self.index)
        self.app.ui_window.protocol('WM_DELETE_WINDOW', lambda: None)
        self.app.page_drag = None
        self.app._page_wheel(None)

    def _warm_pet(self, pet, generation):
        # Decode Spine data during the machine sequence, without touching Tk.
        # First reveal must not synchronously parse/rasterize a new pet model.
        def prepare():
            self.app.data.pet_image(pet.species)
            duration = self.app.data.pet_clip_duration(pet.species, 'dead')
            for index in range(max(1, min(96, math.ceil(duration*30)))):
                if self.closed or generation != self.index:
                    return
                self.app.data.pet_frame(pet.species, 'dead', index, True, fps=30, limit=300)
        Thread(target=prepare, daemon=True, name='lottery-pet-preview').start()

    def start(self):
        self.tick()

    def phase(self, elapsed):
        frame = int(max(0, elapsed)*self.FPS)
        for start, clip, duration in self.schedule:
            if frame < start+duration:
                return clip, frame-start
        start, clip, duration = self.schedule[-1]
        return clip, duration-1

    def dispatch_events(self, elapsed):
        for when, event in self.events:
            if when <= elapsed and (when, event) not in self.played_events:
                self.played_events.add((when, event))
                if event.startswith('SE_UI_'):
                    self.app.audio.effect(event+'.mp3')

    def _draw_at(self, frame, art, point, scale=1.0):
        if art is None:
            return
        origin = art.info.get('origin', (art.width/2, art.height/2))
        if scale != 1:
            art = art.resize((max(1, round(art.width*scale)), max(1, round(art.height*scale))), Image.Resampling.BILINEAR)
        frame.alpha_composite(art, (round(point[0]-origin[0]*scale), round(point[1]-origin[1]*scale)))

    def _pet_pose(self, age):
        pet = self.pets[self.index]
        duration = self.app.data.pet_clip_duration(pet.species, 'dead')
        index = int((age % duration if duration else 0)*30)
        key = pet.species, index
        if key not in self._pet_frames:
            source = self.app.data.pet_frame(pet.species, 'dead', index, True, fps=30, limit=300)
            setup = self.app.data.pet_image(pet.species)
            if source is None or setup is None:
                return None
            ratio = min(190/setup.width, 190/setup.height)*setup.info.get('pixels_per_unit', 1)/source.info.get('pixels_per_unit', 1)
            origin = source.info.get('origin', (source.width/2, source.height))
            art = source.resize((max(1, round(source.width*ratio)), max(1, round(source.height*ratio))), Image.Resampling.LANCZOS)
            art.info['origin'] = (origin[0]*ratio, origin[1]*ratio)
            self._pet_frames[key] = art
            if len(self._pet_frames) > 64:
                self._pet_frames.popitem(last=False)
        else:
            self._pet_frames.move_to_end(key)
        return self._pet_frames[key]

    def show_attributes(self):
        from original_pages import Page
        pet = self.pets[self.index]
        text, visible, resources = self.app._pet_base_fields(pet)
        visible['weixin_Button'] = False
        for label, value in zip(('Life', 'Energy', 'Strength', 'Defense', 'Speed'), pet.stats(self.app.data.tables)):
            text['arrt'+label+'_BitmapFontLabel'] = str(value)
        self.info_page = Page(self.app, 'LuckyDrawPetInfoUI', text=text, visible=visible, resources=resources)
        self.info_page.actions.update({'confirm_Button': self.confirm, 'close_Button': self.confirm})
        self.info_page.publish()
        self.page = self.info_page
        self.ready = True
        self.app.ui_window.protocol('WM_DELETE_WINDOW', self.confirm)

    def render(self, elapsed):
        self.dispatch_events(elapsed)
        frame = self.background.copy()
        clip, index = self.phase(elapsed)
        self._draw_at(frame, self.app.data.armature('niudanji', clip, index, viewport=(800, 480)), (0, 480))
        if elapsed >= self.reveal_at:
            age = elapsed-self.reveal_at
            grow = max(0, min(1, (age-self.LIGHT_SECONDS-self.WAIT_SECONDS)/self.SCALE_SECONDS))
            scale = .2+.8*grow
            point = (400, 245.5)
            glow = self.app.data.armature('ndchongwubeijingguang', 'Animation1', int(age*self.FPS))
            pet_scale = float(self.app.data.tables['Pet'][self.pets[self.index].species].get('scale', 1))
            self._draw_at(frame, glow, point, scale*pet_scale)
            art = self._pet_pose(age)
            if art is not None:
                brightness = max(0, 1-age/self.LIGHT_SECONDS)
                if brightness > 0:
                    white = Image.new('RGBA', art.size, 'white')
                    white.putalpha(art.getchannel('A'))
                    bright = Image.blend(art, white, brightness)
                    bright.info['origin'] = art.info['origin']
                    art = bright
                self._draw_at(frame, art, point, scale)
        if elapsed >= self.info_at:
            if not self.ready:
                self.show_attributes()
            frame.alpha_composite(self.info_page.layer)
        return frame

    def tick(self, *, elapsed=None, schedule=True):
        if self.closed or not self.app.ui_window or not self.app.ui_window.winfo_exists():
            return
        started = time.perf_counter()
        elapsed = time.monotonic()-self.started if elapsed is None else elapsed
        frame = self.render(elapsed)
        self.page.display_frame = frame
        self.app.ui_base_layer = frame
        self.app.ui_art_label.set_layer(frame)
        if schedule:
            self.app.ui_effect_job = self.app.ui_window.after(max(3, round(1000/self.FPS-(time.perf_counter()-started)*1000)), self.tick)

    def confirm(self):
        if not self.ready or self.closed:
            return
        self.index += 1
        if self.index < len(self.pets):
            self.begin_pet()
            self.tick(elapsed=0, schedule=False)
            return
        self.close()
        self.app.lottery_animation = None
        self.app.ui_window.protocol('WM_DELETE_WINDOW', self.app.close_ui)
        if self.back == 'lottery':
            self.app._lottery_page(self.app.ui_body, self.app.ui_info)
        else:
            self.app.close_ui()

    def close(self):
        if not self.closed:
            self.closed = True
            job = getattr(self.app, 'ui_effect_job', None)
            if job:
                try:
                    self.app.ui_window.after_cancel(job)
                except Exception:
                    pass
            self.app.ui_effect_job = None
            self.app.audio.resume_music()
