"""Compare translated Spine 2.1 curve sampling with the original ARM library.

Unicorn is a developer oracle only; no Android runtime ships with the game.
"""
import json
from pathlib import Path
import random
import struct
import sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from spine_animation import curve_percent

emu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
for address, size in [(0, 0xa00000), (0x1000000, 0x10000),
                      (0x2000000, 0x1000), (0x3000000, 0x10000)]:
    emu.mem_map(address, size)
with (ROOT/'research/original-core.so').open('rb') as stream:
    for segment in ELFFile(stream).iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            emu.mem_write(segment['p_vaddr'], segment.data())


def call(address, args):
    emu.reg_write(UC_ARM_REG_SP, 0x1008000)
    emu.reg_write(UC_ARM_REG_LR, 0x2000001)
    for index, value in enumerate(args):
        bits = struct.unpack('<I', struct.pack('<f', value))[0] if isinstance(value, float) else value
        if index < 4:
            emu.reg_write([UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3][index], bits)
        else:
            emu.mem_write(0x1008000+(index-4)*4, struct.pack('<I', bits))
    emu.emu_start(address | 1, 0x2000000, count=20000)
    return struct.unpack('<f', struct.pack('<I', emu.reg_read(UC_ARM_REG_R0)))[0]


emu.mem_write(0x3000008, struct.pack('<I', 0x3001000))
rng, checked = random.Random(441), 0
for _ in range(100):
    curve = [rng.random() for _ in range(4)]
    call(0x40b008, [0x3000000, 0, *curve])
    for percent in [0., .1, .25, .5, .9, 1.]:
        expected = call(0x40b190, [0x3000000, 0, percent])
        actual = curve_percent(curve, percent)
        assert expected == actual, (curve, percent, expected, actual)
        checked += 1
folder = ROOT/'outputs/verification'
folder.mkdir(parents=True, exist_ok=True)
(folder/'spine-curve-arm-comparison.json').write_text(json.dumps({
    'original_set_curve': '0x40b008', 'original_curve_percent': '0x40b190',
    'samples': checked, 'binary32_exact_matches': checked,
    'scope': 'Only Bezier curve lookup; not entire Spine/runtime or battle animation parity'
}, indent=2), encoding='utf-8')
print(f'Spine curve original ARM comparison: {checked}/{checked} exact PASS')
