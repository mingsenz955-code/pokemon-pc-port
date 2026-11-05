"""Sample recovered Cocos Studio bone keyframes in their authored frame units.

Samples the native Cocos TweenType curves used by the recovered exports.
Attachment/z changes are discrete, while transforms and colors interpolate.
"""
import math


def easing(t, kind, params=()):
    # Cocos2d-x 3.x TweenType (also exported by the supplied APK).
    # https://github.com/cocos2d/cocos2d-x/blob/v3/cocos/2d/CCTweenFunction.cpp
    t = max(0.0, min(1.0, t))
    if kind == 0:
        return t
    if kind == -1:
        if len(params) >= 8:
            return ((1-t)**3*params[1]+3*t*(1-t)**2*params[3]
                    +3*t*t*(1-t)*params[5]+t**3*params[7])
        return t
    if kind == 1:
        return 1-math.cos(t*math.pi/2)
    if kind == 2:
        return math.sin(t*math.pi/2)
    if kind == 3:
        return (1-math.cos(t*math.pi))/2
    if 4 <= kind <= 15:
        power, mode = (kind-4)//3+2, (kind-4)%3
        if mode == 0:
            return t**power
        if mode == 1:
            return 1-(1-t)**power
        return (2*t)**power/2 if t < .5 else 1-(2*(1-t))**power/2
    if kind == 16:
        return 0 if t == 0 else 2**(10*(t-1))-.001
    if kind == 17:
        return 1 if t == 1 else 1-2**(-10*t)
    if kind == 18:
        if t in (0, 1):
            return t
        return 2**(20*t-10)/2 if t < .5 else 1-2**(-20*t+10)/2
    if kind == 19:
        return 1-math.sqrt(max(0, 1-t*t))
    if kind == 20:
        return math.sqrt(max(0, 1-(t-1)**2))
    if kind == 21:
        return ((1-math.sqrt(max(0, 1-4*t*t)))/2 if t < .5
                else (math.sqrt(max(0, 1-(2*t-2)**2))+1)/2)
    return t


def sample_frame(frames, time):
    current = max((f for f in frames if f.get('fi', 0) <= time),
                  key=lambda f: f.get('fi', 0), default=frames[0])
    following = next((f for f in frames if f.get('fi', 0) > time), None)
    if following is None or not current.get('tweenFrame', True):
        return current
    span = following['fi']-current.get('fi', 0)
    if span <= 0:
        return current
    factor = easing((time-current.get('fi', 0))/span,
                    current.get('twE', 0), current.get('twEP', ()))
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
