"""Compare native translations with direct execution of ORIGINAL numerical functions.

Unicorn is solely a development test oracle. It is never shipped with the game.
No Android application, OS, JNI, network or third-party code is initialized here.
"""
import json
import random
import struct
import sys
from pathlib import Path

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_CPSR

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
import game_formulas as formulas

emu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
emu.mem_map(0, 0xa00000)
emu.mem_map(0x1000000, 0x10000)
emu.mem_map(0x2000000, 0x1000)
with (ROOT/'research/original-core.so').open('rb') as stream:
    elf = ELFFile(stream)
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            emu.mem_write(segment['p_vaddr'], segment.data())


def original(address, args):
    emu.reg_write(UC_ARM_REG_SP, 0x1008000)
    emu.reg_write(UC_ARM_REG_LR, 0x2000001)
    registers = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]
    for index, value in enumerate(args):
        bits = struct.unpack('<I', struct.pack('<f', value))[0] if isinstance(value, float) else value & 0xffffffff
        if index < 4:
            emu.reg_write(registers[index], bits)
        else:
            emu.mem_write(0x1008000+(index-4)*4, struct.pack('<I', bits))
    emu.emu_start(address | 1, 0x2000000, count=20000)
    result = emu.reg_read(UC_ARM_REG_R0)
    return result-0x100000000 if result & 0x80000000 else result


rng = random.Random(20261101)
checks = [
    ('level_exp', 0x2b5954, lambda: [rng.randint(1, 300)], formulas.level_exp),
    ('attribute_hp', 0x2b598c, lambda: [rng.randint(1, 120), rng.randrange(2, 12)/2, rng.randrange(0, 12)/2, rng.randint(1, 170)], lambda *a: formulas.attribute(*a, hp=True)),
    ('attribute', 0x2b59d8, lambda: [rng.randint(1, 120), rng.randrange(2, 12)/2, rng.randrange(0, 12)/2, rng.randint(1, 170)], formulas.attribute),
    ('train_hp', 0x2b5a1c, lambda: [rng.randint(0, 1000)], formulas.train_hp),
    ('train_mp', 0x2b5a26, lambda: [rng.randint(0, 1000)], formulas.train_mp),
    ('train_attribute', 0x2b5a30, lambda: [rng.randint(0, 1000)], formulas.train_attribute),
    ('train_rate', 0x2b5a3a, lambda: [rng.randint(0, 1000)], formulas.train_rate),
    ('attack_damage', 0x2b5a4c, lambda: [rng.randint(1, 500), rng.randint(1, 500), rng.randint(1, 5), rng.randint(1, 5)], formulas.attack_damage),
    ('defence_damage', 0x2b5aa8, lambda: [rng.randint(1, 500), rng.randint(1, 500), rng.randint(1, 500), rng.randint(1, 5), rng.randint(1, 5)], formulas.defence_damage),
    ('speed_damage', 0x2b5b2c, lambda: [rng.randint(1, 500), rng.randint(1, 500), rng.randint(1, 500), rng.randint(1, 5), rng.randint(1, 5)], formulas.speed_damage),
    ('energy_damage', 0x2b5b98, lambda: [rng.randint(1, 500), rng.randint(1, 500), rng.randint(1, 5), rng.randint(1, 5)], formulas.energy_damage),
    ('skill_damage', 0x2b5c08, lambda: [rng.randint(0, 500), rng.randint(0, 500), rng.randint(0, 500)], formulas.skill_damage),
    ('escape_rate', 0x2b5c3c, lambda: [rng.randint(1, 300), rng.randint(1, 300)], formulas.escape_rate),
    ('offer_exp', 0x2b5c54, lambda: [rng.randint(1, 170), rng.randrange(1, 30)/10, rng.randint(-5, 20)], formulas.offer_exp),
    ('shared_exp', 0x2b5cdc, lambda: [rng.randint(1, 170), rng.randrange(1, 30)/10, rng.randint(-5, 20), rng.randint(1, 6)], formulas.shared_exp),
]
report = {}
for name, address, generate, native in checks:
    mismatches = []
    for _ in range(200):
        args = generate()
        expected, actual = original(address, args), native(*args)
        if actual != expected:
            mismatches.append({'args': args, 'original': expected, 'native': actual})
    report[name] = {'samples': 200, 'mismatches': mismatches, 'original_address': hex(address)}
    print(name, 'PASS' if not mismatches else f'FAIL {mismatches[:3]}')
output = ROOT/'outputs/verification/original-formula-comparison.json'
output.write_text(json.dumps(report, indent=2), encoding='utf-8')
assert all(not r['mismatches'] for r in report.values()), output
