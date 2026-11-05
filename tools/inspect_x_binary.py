"""Read-only inspection of named functions in the supplied X 2.10.9 engine."""
import argparse
import struct
from types import SimpleNamespace
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM
from elftools.elf.elffile import ELFFile
from inspect_binary import instructions

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('queries', nargs='+')
parser.add_argument('--size', type=lambda value:int(value,0), default=1024)
args = parser.parse_args()
class RawSymbol(dict):
    name = 'raw_function'
with (ROOT/'research/apk-x-2.10.9/lib/armeabi/libcocos2dcpp.so').open('rb') as stream:
    elf = ELFFile(stream)
    symbols = list(elf.get_section_by_name('.dynsym').iter_symbols())
    lookup = {s['st_value'] & ~1: s.name for s in symbols if s['st_value']}
    segments = [(s['p_vaddr'], s.data()) for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
    def read(address, count):
        for start, content in segments:
            if start <= address < start+len(content):
                return content[address-start:address-start+count]
        return b''
    reloc, plt = elf.get_section_by_name('.rel.plt'), elf.get_section_by_name('.plt')
    if reloc and plt:
        dynsym = elf.get_section_by_name('.dynsym')
        for i, r in enumerate(reloc.iter_relocations()):
            lookup[plt['sh_addr']+20+12*i] = dynsym.get_symbol(r['r_info_sym']).name
    raw_targets = [RawSymbol(st_value=int(q, 0), st_size=args.size) for q in args.queries if q.startswith('0x')]
    for symbol in symbols+raw_targets:
        if not symbol['st_size'] or (not isinstance(symbol, RawSymbol) and not any(q in symbol.name for q in args.queries)):
            continue
        address = symbol['st_value'] & ~1
        decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB if symbol['st_value'] & 1 else CS_MODE_ARM)
        print('\n'+symbol.name+' @ '+hex(address))
        literals = {}
        for op in instructions(decoder, read, address, symbol['st_size'], flow=True):
            note = ''
            if op.mnemonic in ('bl', 'blx', 'b.w', 'b') and op.op_str.startswith('#'):
                target = int(op.op_str[1:], 0) & ~1
                note = lookup.get(target, '')
                veneer = read(target, 16)
                if len(veneer) == 16 and veneer[:4] == bytes.fromhex('7847c046'):
                    resolved = target+16+struct.unpack('<i', veneer[12:16])[0]
                    note = lookup.get(resolved, hex(resolved))
            if '[pc, #' in op.op_str:
                off = int(op.op_str.split('[pc, #')[1].split(']')[0], 0)
                literal = ((op.address+4) & ~3)+off
                raw = read(literal, 4)
                if len(raw) == 4:
                    value = struct.unpack('<I', raw)[0]
                    literals[op.op_str.split(',')[0]] = value
                    note += ' literal='+hex(value)+' float='+str(struct.unpack('<f', raw)[0])
            if op.mnemonic in ('add', 'add.w') and op.op_str.endswith(', pc'):
                reg = op.op_str.split(',')[0]
                if reg in literals:
                    target = (literals[reg]+op.address+4) & 0xffffffff
                    raw = read(target, 100).split(b'\0')[0]
                    if raw and all(32 <= b < 127 for b in raw):
                        note += ' string='+repr(raw.decode('ascii'))
            print(hex(op.address), op.mnemonic, op.op_str, note)
