"""SkillEffect Armatures and authored frame callbacks from 1.20.4.

BattleController::showSkillEffectNormal 0x2c74a4 loads Skill/<path>.ExportJson,
plays Animation1 once, and attaches to p_center/bodyPos=1 or p_shadow.
Special controllers: 1=front/back, 2=directional, 3=world-position,
4=six horizontal MoveBy actions, 5=healing (native 0x2c57d0..0x2c74a4).
"""
from functools import lru_cache
from PIL import Image
from armature_composite import composite, transform_art


class BattleEffects:
    def __init__(self, data):
        self.data = data

    @lru_cache(maxsize=128)
    def plan(self, skill_id, side):
        skill = self.data.tables['Skill'].get(str(skill_id), {})
        row = self.data.tables['SkillEffect'].get(str(skill.get('skillEffectTypeId', '')), {})
        effect_type = int(row.get('effectType', -1))
        if not row or effect_type not in range(6):
            return None
        # path2 is a rear layer for type 1, or an encoded secondary effect.
        # It is not the enemy's alternative to path1.
        path = row.get('path1')
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
        hits = tuple(frame*25/60 for frame, name in events if name in ('attack', 'add'))
        hit = hits[0] if hits else None
        return {'path': path, 'duration': duration, 'hit': hit,
                'hits': hits, 'type': effect_type, 'skill_id': str(skill_id),
                'rear_path': row.get('path2') if effect_type == 1 else None,
                'events': tuple((frame*25/60, name) for frame, name in events),
                'bone': 'p_center' if int(skill.get('bodyPos', 1)) == 1 else 'p_shadow',
                'self_target': int(skill.get('effectpos', 1)) == 2,
                'scale_with_pet': int(row.get('effectScale', 0)) != 0,
                'hide_ui': int(row.get('hideUI', 0)) != 0, 'sound': row.get('sound', '')}

    def plan_effect(self, effect_id, self_target=True):
        """Build a plan for a PetItem SkillEffect row (outside the Skill table)."""
        row = self.data.tables.get('SkillEffect', {}).get(str(effect_id), {})
        effect_type = int(row.get('effectType', -1))
        if not row or effect_type not in range(6):
            return None
        path = row.get('path1')
        _, source = self.data.armature_source(path)
        if not source:
            return None
        moves = (source.get('animation_data') or [{}])[0].get('mov_data', [])
        move = next((m for m in moves if m.get('name') == 'Animation1'), None)
        if not move:
            return None
        events = sorted({(int(f.get('fi', 0)), f['evt'])
                         for b in move.get('mov_bone_data', []) for f in b.get('frame_data', [])
                         if f.get('evt')})
        duration = max(1, int(move.get('dr', 1)))*25/60
        hits = tuple(frame*25/60 for frame, name in events if name in ('attack', 'add'))
        return {'path': path, 'duration': duration, 'hit': hits[0] if hits else None,
                'hits': hits, 'type': effect_type, 'skill_id': str(effect_id),
                'rear_path': row.get('path2') if effect_type == 1 else None,
                'events': tuple((frame*25/60, name) for frame, name in events),
                'bone': 'p_center', 'self_target': bool(self_target),
                'scale_with_pet': int(row.get('effectScale', 0)) != 0,
                'hide_ui': int(row.get('hideUI', 0)) != 0, 'sound': row.get('sound', '')}

    def draw(self, frame, ui, rear=False):
        action = ui.anim
        if not action or not action.get('effect'):
            return
        plan = action['effect']
        index = int(action['age']*60/25)
        path = plan.get('rear_path') if rear else plan['path']
        if not path:
            return
        art = self._scaled_art(path, index, frame.width/800)
        if art is None:
            return
        side = action['side'] if plan['self_target'] else ('enemy' if action['side'] == 'player' else 'player')
        point = ui.pet_bones.get(side, {}).get(plan['bone'], ui.pet_positions[side])
        if plan['type'] == 2 and plan['skill_id'] == '300025':
            # Native 0x2c6ac6: full-screen noise is centered at winSize/2+(0,21).
            point = (frame.width/2, frame.height/2-21*frame.width/800)
        if plan['type'] == 4:
            # Native 0x2c60ec: six alternating +/-84 moves, each 0.4 seconds.
            phase = min(6.0, action['age']/25/.4)
            segment = min(5, int(phase))
            amount = phase-segment
            distance = (amount if segment % 2 == 0 else 1-amount)*84
            point = (point[0]+distance*frame.width/800*(1 if side == 'player' else -1), point[1])
        unit = ui.presentation_unit(side == 'enemy')
        pet_scale = float(self.data.tables['Pet'][unit.pet.species].get('effectScale', 1)) if unit and plan['scale_with_pet'] else 1
        scale = pet_scale
        origin = art.info.get('origin', (art.width/2, art.height/2))
        ox, oy = origin[0]*scale, origin[1]*scale
        if scale != 1:
            art = transform_art(art, scale)
        if plan['type'] == 2 and side == 'player':
            art = transform_art(art, rotate=True)
            ox, oy = art.width-ox, art.height-oy
        composite(frame, art, (round(point[0]-ox), round(point[1]-oy)))

    @lru_cache(maxsize=96)
    def _scaled_art(self, path, index, scale):
        from battle_animation_cache import cached_frame
        cached = cached_frame(self.data, path, index, scale)
        if cached is not None:
            return cached
        _, source = self.data.armature_source(path)
        moves = (source.get('animation_data') or [{}])[0].get('mov_data', []) if source else []
        move = next((m for m in moves if m.get('name') == 'Animation1'), {})
        if index < 0 or index >= int(move.get('dr', 0)):
            return None
        art = self.data.armature(path, 'Animation1', index, layered=True)
        if art is None or scale == 1:
            return art
        return transform_art(art, scale)


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
