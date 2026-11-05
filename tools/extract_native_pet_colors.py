"""Read static Color3B initializers from the supplied APK, without executing it."""
import json
import re
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from elftools.elf.elffile import ELFFile
ROOT = Path(__file__).resolve().parent.parent
with (ROOT/'research/apk-x-2.10.9/lib/armeabi/libcocos2dcpp.so').open('rb') as stream:
    elf = ELFFile(stream)
    segments = [(s['p_vaddr'], s.data()) for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
    def word(address):
        for base, data in segments:
            if base <= address <= base+len(data)-4:
                return struct.unpack_from('<I', data, address-base)[0]
        return None
    def read(address, size):
        for base, data in segments:
            if base <= address < base+len(data):
                return data[address-base:address-base+size]
        return b''
    symbols = list(elf.get_section_by_name('.dynsym').iter_symbols())
    colors = {s['st_value']: s.name for s in symbols if 'FONT_COLOR_' in s.name}
    raw = elf.get_section_by_name('.init_array').data()
    starts = sorted({v & ~1 for v in struct.unpack('<'+'I'*(len(raw)//4), raw) if v})
    found = {}
    for start, end in zip(starts, starts[1:]+[starts[-1]+1024]):
        registers = {}
        def value(token, address):
            token = token.strip()
            return (address+4 if token == 'pc' else
                    int(token[1:], 0) if token.startswith('#') else registers.get(token))
        for op in Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(read(start, end-start), start):
            tokens = [p.strip() for p in op.op_str.split(',')]
            name = op.mnemonic.split('.')[0]
            try:
                if name in ('mov', 'movs'):
                    registers[tokens[0]] = value(tokens[1], op.address)
                elif name in ('add', 'adds', 'sub', 'subs', 'lsl', 'lsls'):
                    a, b = (value(tokens[0], op.address), value(tokens[1], op.address)) if len(tokens) == 2 else (value(tokens[1], op.address), value(tokens[2], op.address))
                    result = None if a is None or b is None else (a << b if name.startswith('lsl') else a-b if name.startswith('sub') else a+b)
                    registers[tokens[0]] = result & 0xffffffff if result is not None else None
                elif name == 'ldr':
                    expression = op.op_str.split('[', 1)[1].split(']')[0]
                    parts = [p.strip() for p in expression.split(',')]
                    a = value(parts[0], op.address)
                    if parts[0] == 'pc':
                        a &= ~3
                    b = value(parts[1], op.address) if len(parts) > 1 else 0
                    registers[tokens[0]] = word((a+b) & 0xffffffff) if a is not None and b is not None else None
                elif name == 'bl':
                    target = int(tokens[0][1:], 0) & ~1
                    if target == 0x47252e and registers.get('r0') in colors:
                        found[colors[registers['r0']]] = {'rgb': [registers.get('r'+str(i)) for i in (1, 2, 3)], 'call': hex(op.address), 'initializer': hex(start)}
                    for register in ('r0', 'r1', 'r2', 'r3'):
                        registers[register] = None
            except (ValueError, IndexError, TypeError):
                registers.pop(tokens[0], None)
    path = ROOT/'outputs/verification/0.2.97/native-font-colors.json'
    path.write_text(json.dumps(found, indent=2), encoding='utf-8')
    print(json.dumps(found, indent=2))
