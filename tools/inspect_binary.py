"""Read-only ARM/Thumb function inspection for documenting original game formulas."""
import argparse
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parent.parent


def instructions(decoder, read, address, size, flow=False):
    if not flow:
        return decoder.disasm(read(address, size), address)
    # Follow code branches instead of decoding inline literal pools as Thumb
    # instructions. Do not follow calls into another function.
    found, pending = {}, [address]
    while pending:
        current = pending.pop()
        while address <= current < address+size and current not in found:
            op = next(decoder.disasm(read(current, 4), current, count=1), None)
            if op is None:
                break
            found[current] = op
            name = op.mnemonic
            if name.startswith('b') and name not in ('bl', 'blx', 'bic', 'bics', 'bfi', 'bfc') or name in ('cbz', 'cbnz'):
                operand = op.op_str.split(',')[-1].strip()
                if operand.startswith('#'):
                    pending.append(int(operand[1:], 0) & ~1)
                if name in ('b', 'b.w', 'bx'):
                    break
            if (name in ('pop', 'pop.w', 'ldm', 'ldm.w') and 'pc' in op.op_str) or name in ('tbb', 'tbh'):
                break
            current += op.size
    return (found[key] for key in sorted(found))


def inspect(queries, flow=False, address=None, size=1024):
    requested_address = address
    symbols = json.loads((ROOT/'research/demangled-symbols.json').read_text(encoding='utf-8'))
    with (ROOT/'research/original-core.so').open('rb') as stream:
        elf = ELFFile(stream)
        segments = [(s['p_vaddr'], s['p_memsz'], s.data()) for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
        def read(address, count):
            for va, size, content in segments:
                if va <= address < va+size:
                    return content[address-va:address-va+count]
            return b''
        lookup = {s['address'] & ~1: s['demangled'] for s in symbols}
        reloc = elf.get_section_by_name('.rel.plt')
        plt = elf.get_section_by_name('.plt')
        dynsym = elf.get_section_by_name('.dynsym')
        if reloc and plt:
            for i, r in enumerate(reloc.iter_relocations()):
                lookup[plt['sh_addr']+20+12*i] = dynsym.get_symbol(r['r_info_sym']).name
        targets = symbols if requested_address is None else [{'address': requested_address, 'size': size, 'demangled': f'raw_{requested_address:x}'}]
        for sym in targets:
            if requested_address is None and not any(q in sym['demangled'] for q in queries):
                continue
            address = sym['address'] & ~1
            mode = CS_MODE_THUMB if sym['address'] & 1 else CS_MODE_ARM
            decoder = Cs(CS_ARCH_ARM, mode)
            print(f'\n{sym["demangled"]} @ {address:x}, {sym["size"]} bytes')
            for op in instructions(decoder, read, address, sym['size'], flow):
                note = ''
                if op.mnemonic in ['bl', 'blx', 'b.w', 'b'] and op.op_str.startswith('#'):
                    target = int(op.op_str[1:], 0) & ~1
                    note = lookup.get(target, '')
                    veneer = read(target, 16)
                    if len(veneer) == 16 and veneer[:4] == bytes.fromhex('7847c046'):
                        resolved = target+16+struct.unpack('<i', veneer[12:16])[0]
                        note = lookup.get(resolved, hex(resolved))
                if '[pc, #' in op.op_str:
                    imm = op.op_str.split('[pc, #')[1].split(']')[0]
                    off = int(imm, 0)
                    literal = ((op.address+4) & ~3)+off if mode == CS_MODE_THUMB else op.address+8+off
                    data = read(literal, 8)
                    if len(data) >= 4:
                        note += f' literal@{literal:x}={data.hex()} int={struct.unpack("<I",data[:4])[0]} f32={struct.unpack("<f",data[:4])[0]:g}'
                        if len(data) == 8:
                            note += f' f64={struct.unpack("<d",data)[0]:g}'
                print(f'  {op.address:08x}: {op.mnemonic:10s} {op.op_str:30s} {note}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('queries', nargs='*')
    parser.add_argument('--address', type=lambda value: int(value, 0), help='Raw address, with Thumb bit when needed')
    parser.add_argument('--size', type=lambda value: int(value, 0), default=1024)
    parser.add_argument('--flow', action='store_true', help='Follow branches around inline literal pools')
    args = parser.parse_args()
    if not args.queries and args.address is None:
        parser.error('Provide a symbol query or --address')
    inspect(args.queries, args.flow, args.address, args.size)
