"""Spine 2.1 JSON timeline sampling for the original recovered assets.

Bone transforms, slot attachment/color, mesh deformation and draw order.
IK/inheritance constraints are tracked separately; this is not full runtime parity.
"""
import bisect
import copy
from functools import lru_cache
from game_formulas import add, sub, mul, div, f32


def duration(animation):
    if isinstance(animation, list):
        return max((duration(v) for v in animation), default=0.0)
    if isinstance(animation, dict):
        return max([float(animation.get('time', 0))]+
                   [duration(v) for k, v in animation.items() if k != 'time'])
    return 0.0


@lru_cache(maxsize=512)
def curve_points(curve):
    cx1, cy1, cx2, cy2 = map(f32, curve)
    step = f32(.1)
    step2, step3 = mul(step, step), mul(mul(step, step), step)
    pre1, pre2, pre4, pre5 = mul(3, step), mul(3, step2), mul(6, step2), mul(6, step3)
    def axis(c1, c2):
        tmp1, tmp2 = add(mul(-c1, 2), c2), add(mul(sub(c1, c2), 3), 1)
        delta = add(add(mul(c1, pre1), mul(tmp1, pre2)), mul(tmp2, step3))
        delta2, delta3 = add(mul(tmp1, pre4), mul(tmp2, pre5)), mul(tmp2, pre5)
        value, values = delta, []
        for _ in range(9):
            values.append(value)
            delta = add(delta, delta2)
            delta2 = add(delta2, delta3)
            value = add(value, delta)
        return values
    return tuple(zip(axis(cx1, cx2), axis(cy1, cy2)))


def curve_percent(curve, percent):
    if curve == 'stepped':
        return 0.0
    if not isinstance(curve, list):
        return percent
    # Original Spine 2.1 uses a 10-segment lookup, not an analytic Bezier solve.
    percent, px, py = f32(percent), 0.0, 0.0
    for x, y in curve_points(tuple(curve))+((1.0, 1.0),):
        if x >= percent:
            return add(py, div(mul(sub(y, py), sub(percent, px)), sub(x, px))) if x != px else y
        px, py = x, y
    return 1.0


def frames_at(frames, seconds):
    if not frames or seconds < float(frames[0].get('time', 0)):
        return None
    index = bisect.bisect_right([float(v.get('time', 0)) for v in frames], seconds)-1
    first = frames[index]
    if index == len(frames)-1:
        return first, first, 0.0
    second = frames[index+1]
    gap = float(second.get('time', 0))-float(first.get('time', 0))
    p = (seconds-float(first.get('time', 0)))/gap if gap else 0
    return first, second, curve_percent(first.get('curve'), p)


def channels(frames, seconds, keys, defaults, angle=False):
    sampled = frames_at(frames, seconds)
    if sampled is None:
        return None
    first, second, fraction = sampled
    result = []
    for key, default in zip(keys, defaults):
        a, b = float(first.get(key, default)), float(second.get(key, default))
        delta = (b-a+180)%360-180 if angle else b-a
        result.append(a+delta*fraction)
    return result


def deformation(frames, seconds, count):
    sampled = frames_at(frames, seconds)
    if sampled is None:
        return [0.0]*count
    def expand(frame):
        result = [0.0]*count
        offset = int(frame.get('offset', 0))
        values = frame.get('vertices', [])
        if offset < 0 or offset+len(values) > count:
            raise ValueError('Spine FFD frame exceeds attachment vertex count')
        result[offset:offset+len(values)] = values
        return result
    first, second, fraction = sampled
    return [a+(b-a)*fraction for a, b in zip(expand(first), expand(second))]


def sample_pose(setup, animation_name, seconds, loop=True):
    animation = setup.get('animations', {}).get(animation_name)
    if animation is None:
        raise ValueError(f'Original animation {animation_name!r} is missing')
    length = duration(animation)
    seconds = seconds % length if loop and length else min(seconds, length)
    pose = copy.deepcopy(setup)
    bones = {b['name']: b for b in pose['bones']}
    for name, timelines in animation.get('bones', {}).items():
        bone = bones[name]
        for kind, frames in timelines.items():
            if kind == 'rotate':
                values = channels(frames, seconds, ['angle'], [0], angle=True)
                if values is not None:
                    bone['rotation'] = bone.get('rotation', 0)+values[0]
            elif kind == 'translate':
                values = channels(frames, seconds, ['x', 'y'], [0, 0])
                if values is not None:
                    for key, value in zip(('x', 'y'), values):
                        bone[key] = bone.get(key, 0)+value
            elif kind == 'scale':
                values = channels(frames, seconds, ['x', 'y'], [1, 1])
                if values is not None:
                    for key, value in zip(('scaleX', 'scaleY'), values):
                        bone[key] = bone.get(key, 1)*value
            else:
                raise NotImplementedError(f'Original Spine bone timeline {kind}')
    slots = {s['name']: s for s in pose.get('slots', [])}
    for name, timelines in animation.get('slots', {}).items():
        slot = slots[name]
        attachment = frames_at(timelines.get('attachment', []), seconds)
        if attachment is not None:
            slot['attachment'] = attachment[0].get('name')
        color = frames_at(timelines.get('color', []), seconds)
        if color is not None:
            first, second, fraction = color
            def rgba(frame):
                value = frame.get('color', 'ffffffff')
                return [int(value[i:i+2], 16) for i in range(0, 8, 2)]
            slot['color'] = ''.join(f'{round(a+(b-a)*fraction):02x}'
                                   for a, b in zip(rgba(first), rgba(second)))
    for skin_name, slot_rows in animation.get('ffd', {}).items():
        for slot_name, attachment_rows in slot_rows.items():
            for name, frames in attachment_rows.items():
                attachment = pose['skins'][skin_name][slot_name][name]
                raw = attachment.get('vertices', [])
                if attachment.get('type', 'region') in ('weightedmesh', 'skinnedmesh'):
                    indices, cursor = [], 0
                    while cursor < len(raw):
                        count = int(raw[cursor])
                        cursor += 1
                        for _ in range(count):
                            indices.extend((cursor+1, cursor+2))
                            cursor += 4
                    for index, delta in zip(indices, deformation(frames, seconds, len(indices))):
                        raw[index] += delta
                else:
                    attachment['vertices'] = [a+b for a, b in
                                              zip(raw, deformation(frames, seconds, len(raw)))]
    order = frames_at(animation.get('drawOrder', animation.get('draworder', [])), seconds)
    if order is not None:
        original = list(pose['slots'])
        indices = {s['name']: i for i, s in enumerate(original)}
        arranged, unchanged, cursor = [None]*len(original), [], 0
        for offset in order[0].get('offsets', []):
            index = indices[offset['slot']]
            while cursor < index:
                unchanged.append(original[cursor])
                cursor += 1
            arranged[index+int(offset['offset'])] = original[index]
            cursor += 1
        unchanged.extend(original[cursor:])
        for index in range(len(arranged)-1, -1, -1):
            if arranged[index] is None:
                arranged[index] = unchanged.pop()
        pose['slots'] = arranged
    return pose
