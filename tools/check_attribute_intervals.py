"""Compare the recovered interval helper against its actual ARM instructions.

Only JSON getters and RNG are replaced by controlled inputs. Arithmetic runs
in the original binary. No original executable is used by the shipped game.
"""
import json
import random
import struct
import sys
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from pet_factory import _attribute_roll

emu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
emu.mem_map(0, 0xa00000)
emu.mem_map(0x1000000, 0x10000)
emu.mem_map(0x2000000, 0x1000)
with (ROOT/'research/original-core.so').open('rb') as stream:
    elf = ELFFile(stream)
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            emu.mem_write(segment['p_vaddr'], segment.data())

inputs = {}
def external(uc, address, size, data):
    if address == 0x2b9ebc:
        value = inputs['low'] if uc.reg_read(UC_ARM_REG_R0) == 0x1001100 else inputs['high']
        low, high = struct.unpack('<II', struct.pack('<d', value))
        uc.reg_write(UC_ARM_REG_R0, low)
        uc.reg_write(UC_ARM_REG_R1, high)
    elif address == 0x46c954:
        uc.reg_write(UC_ARM_REG_R0, 0x1001200)
    elif address == 0x2b9428:
        uc.reg_write(UC_ARM_REG_R0, inputs['draw'])
    else:
        return
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

emu.hook_add(UC_HOOK_CODE, external)
class ControlledRandom:
    def random(self):
        return 0.0
    def getrandbits(self, count):
        assert count == 32
        return inputs['draw']

rng = random.Random(20509)
count = 0
for low, high in [(0., 0.), (0., 1.), (4., 4.5), (4.5, 5.5), (5., 5.)]:
    for draw in [0, 1, 0x7fffffff, 0xffffffff]+[rng.getrandbits(32) for _ in range(100)]:
        inputs.update(low=low, high=high, draw=draw)
        emu.mem_write(0x1001000, struct.pack('<I', 0x1001100))
        emu.reg_write(UC_ARM_REG_R0, 0x1001000)
        emu.reg_write(UC_ARM_REG_SP, 0x1008000)
        emu.reg_write(UC_ARM_REG_LR, 0x2000001)
        emu.emu_start(0x2ba827, 0x2000000, count=20000)
        expected = emu.reg_read(UC_ARM_REG_R0)
        actual = struct.unpack('<I', struct.pack('<f', _attribute_roll(ControlledRandom(), [[low, high]], [1])))[0]
        assert expected == actual, (low, high, draw, hex(expected), hex(actual))
        count += 1
print(f'Attribute interval ARM comparison: {count} / {count} PASS')
