"""Native Python translations of standalone formulas from the 1.20.4 ARM core.

Every arithmetic operation rounds to IEEE-754 binary32, as in the original
soft-float code. These functions have a separate original-binary oracle test.
The Android binary and CPU emulator are NOT used by the shipped application.
"""
import struct


def f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]


def add(a, b):
    return f32(f32(a)+f32(b))


def sub(a, b):
    return f32(f32(a)-f32(b))


def mul(a, b):
    return f32(f32(a)*f32(b))


def div(a, b):
    return f32(f32(a)/f32(b))


def level_exp(level):
    return int(mul(mul(level, 50), add(div(level, 400), .2)))


def hatch_exp(experience):
    return max(1, int(mul(experience, .3)))


def free_pet_gold(star_level):
    """Formula_FreePetGoldCount: 300 gold per authored Pet.starLevel."""
    return 300*int(star_level)


def attribute(base, variation, growth, level, hp=False):
    rate = mul(add(base, variation), growth)
    if hp:
        rate = mul(rate, 1.8)
    return int(add(base, mul(div(rate, 100), level)))


def train_hp(value):
    return int(value/5)


def train_mp(value):
    return int(value/10)


def train_attribute(value):
    return int(value/20)


def train_rate(value):
    return int(value/5)+15


def attack_damage(a, b, c, d):
    return max(1, int(mul(sub(mul(a, 1.35), b), sub(add(c, 1), d)))+6)


def defence_damage(a, b, c, d, e):
    return max(1, int(add(mul(sub(mul(a, 1.35), mul(add(mul(b, .5), c), .25)),
                              sub(add(d, 1), e)), 6)))


def speed_damage(a, b, c, d, e):
    return max(1, int(add(mul(sub(mul(a, 1.35), mul(b+c, .5)),
                              sub(add(d, 1), e)), 6)))


def energy_damage(a, b, c, d):
    return max(1, int(add(mul(sub(add(div(a, 5), div(a, 5)), div(b, 5)),
                              sub(add(c, 1), d)), 6)))


def skill_damage(a, b, c):
    return max(1, int(add(b, div(a*c, 100))))


def escape_rate(a, b):
    return max(30, min(90, (a-b+45)*2))


def offer_exp(level, rate, reduction):
    n = int(mul(div(mul(level, 50), add(mul(level-1, .3), 3.5)), rate))
    penalty = 0 if reduction <= 0 else .9 if reduction > 9 else mul(reduction, .1)
    return int(sub(n, mul(n, penalty)))


def shared_exp(level, rate, reduction, participants):
    n = offer_exp(level, rate, reduction)
    return int(div(add(n, mul(n, mul(participants-1, .18))), participants))
