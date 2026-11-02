"""Normal SkillEffect Armatures and authored frame callbacks from 1.20.4.

BattleController::showSkillEffectNormal 0x2c74a4 loads Skill/<path>.ExportJson,
plays Animation1 once, and attaches to p_center/bodyPos=1 or p_shadow.
Travel/projectile effectType 1..5 still need their separate native actions.
"""
from functools import lru_cache
from PIL import Image


class BattleEffects:
    def __init__(self, data):
        self.data = data

    @lru_cache(maxsize=128)
    def plan(self, skill_id, side):
        skill = self.data.tables['Skill'].get(str(skill_id), {})
        row = self.data.tables['SkillEffect'].get(str(skill.get('skillEffectTypeId', '')), {})
        if not row or int(row.get('effectType', -1)) != 0:
            return None
        path = row.get('path1' if side == 'player' else 'path2') or row.get('path1')
        _, source = self.data.armature_source(path)
        if not source:
            return None
        moves = (source.get('animation_data') or [{}])[0].get('mov_data', [])
        move = next((m for m in moves if m.get('name') == 'Animation1'), None)
        if not move:
            return None
        events = sorted({(int(f.get('fi', 0)), f['evt'])
                         for b in move.get('mov_bone_data', []) for f in b.get('frame_data', []) if f.get('evt')})
        # Cocos Armature uses its 60 Hz animation interval. Internal battle UI
        # ages remain in 25 Hz units for compatibility with the host clock.
        duration = max(1, int(move.get('dr', 1)))*25/60
        hit = next((frame*25/60 for frame, name in events if name == 'attack'), None)
        return {'path': path, 'duration': duration, 'hit': hit,
                'events': tuple((frame*25/60, name) for frame, name in events),
                'bone': 'p_center' if int(skill.get('bodyPos', 1)) == 1 else 'p_shadow',
                'self_target': int(row.get('posType', 1)) == 2,
                'scale_with_pet': int(row.get('effectScale', 0)) != 0,
                'hide_ui': int(row.get('hideUI', 0)) != 0, 'sound': row.get('sound', '')}

    def draw(self, frame, ui):
        action = ui.anim
        if not action or not action.get('effect'):
            return
        plan = action['effect']
        index = int(action['age']*60/25)
        art = self.data.armature(plan['path'], 'Animation1', index)
        if art is None:
            return
        side = action['side'] if plan['self_target'] else ('enemy' if action['side'] == 'player' else 'player')
        point = ui.pet_bones.get(side, {}).get(plan['bone'], ui.pet_positions[side])
        unit = ui.presentation_unit(side == 'enemy')
        pet_scale = float(self.data.tables['Pet'][unit.pet.species].get('effectScale', 1)) if unit and plan['scale_with_pet'] else 1
        scale = frame.width/800*pet_scale
        origin = art.info.get('origin', (art.width/2, art.height/2))
        ox, oy = origin[0]*scale, origin[1]*scale
        art = art.resize((max(1, round(art.width*scale)), max(1, round(art.height*scale))), Image.Resampling.LANCZOS)
        if action['side'] == 'enemy':
            art = art.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            ox = art.width-ox
        frame.alpha_composite(art, (round(point[0]-ox), round(point[1]-oy)))


class EffectAudio:
    """One nonblocking Windows MCI channel for original skill MP3 files."""
    def __init__(self, data):
        self.folder = data.assets/'Audio'

    def play(self, filename):
        import os
        if os.name != 'nt' or not filename:
            return
        path = self.folder/filename
        if not path.is_file():
            return
        import ctypes
        send = ctypes.windll.winmm.mciSendStringW
        send('close pocket_skill_effect', None, 0, None)
        error = send(f'open "{path.resolve()}" type mpegvideo alias pocket_skill_effect', None, 0, None)
        if not error:
            send('play pocket_skill_effect from 0', None, 0, None)
