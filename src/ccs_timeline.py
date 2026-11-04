"""Sample recovered Cocos Studio bone keyframes in their authored frame units.

Linear tweenFrame tracks are supported; other easing modes remain pending.
Attachment/z changes are discrete, while transforms and colors interpolate.
"""
import math


def sample_frame(frames, time):
    current = max((f for f in frames if f.get('fi', 0) <= time),
                  key=lambda f: f.get('fi', 0), default=frames[0])
    following = next((f for f in frames if f.get('fi', 0) > time), None)
    if following is None or not current.get('tweenFrame', True) or current.get('twE', 0) != 0:
        return current
    span = following['fi']-current.get('fi', 0)
    if span <= 0:
        return current
    factor = (time-current.get('fi', 0))/span
    result = dict(current)
    for key in ('x', 'y', 'cX', 'cY', 'kX', 'kY'):
        default = 1 if key in ('cX', 'cY') else 0
        start, end = current.get(key, default), following.get(key, default)
        delta = end-start
        if key in ('kX', 'kY'):
            delta = (delta+math.pi) % (2*math.pi)-math.pi
        result[key] = start+delta*factor
    if 'color' in current or 'color' in following:
        result['color'] = {key: current.get('color', {}).get(key, 255)+factor*(
            following.get('color', {}).get(key, 255)-current.get('color', {}).get(key, 255))
            for key in ('a', 'r', 'g', 'b')}
    return result
