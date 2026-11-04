#!/usr/bin/env python3
# Apply an Atmosphère-layout mod to an extracted game: <mod>/exefs (code modules that replace or join the game's, *.ips patches named by the build ID they patch), <mod>/exefs_patches/*/*.ips
# (Atmosphère's own patch folder) and <mod>/romfs (files laid over the game's RomFS, as LayeredFS does). The output is an extraction like the one it was made from: ExeFS with every patched or
# added module written as an uncompressed NSO, RomFS.img with the mod's files merged in (romfs_image.py pack_layers), control.nacp and icon.jpg.
# Modules a mod adds are often linked against the game's at fixed distances: Luminescent Platinum's subsdk1 makes 1,228 direct B/BL into main, and its IPS on main branches into subsdk1.
# Horizon's loader puts the modules one after another (main, subsdk0..9, sdk; each image + bss rounded up to a page), so the tool reports each added module's offset from main in that layout;
# the profile's module_at key has the host map the module there (loader.c "Modules at fixed offsets from main").
# Usage: mod_apply.py <extraction> <mod folder> <out extraction>; prints the profile keys: "modules\t<names>" and "module_at\t<name>=<offset> ..."
import os, re, shutil, struct, sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nso, romfs_image

ORDER = ['main'] + [f'subsdk{i}' for i in range(10)] + ['sdk']   # Horizon's load order (rtld goes first and is replaced by the host)
PAGE = 0x1000


def is_nso(p): return p.is_file() and p.read_bytes()[:4] == b'NSO0'


def ips_records(data, what):
    """[(file offset, bytes)] of an IPS or IPS32 patch; offsets count from the start of the uncompressed NSO file (its 0x100-byte header included), as Atmosphère applies them"""
    if data[:5] == b'IPS32': wide, i, end = True, 5, b'EEOF'
    elif data[:5] == b'PATCH': wide, i, end = False, 5, b'EOF'
    else: sys.exit(f'[RED] {what}: not an IPS patch (magic {data[:5]!r})')
    out, n = [], 4 if wide else 3
    while data[i:i + len(end)] != end:
        if i + n + 2 > len(data): sys.exit(f'[RED] {what}: cut short at {i:#x} (no end marker)')
        off = int.from_bytes(data[i:i + n], 'big'); size = int.from_bytes(data[i + n:i + n + 2], 'big'); i += n + 2
        if size: out.append((off, data[i:i + size])); i += size
        else: out.append((off, data[i + 2:i + 3] * int.from_bytes(data[i:i + 2], 'big'))); i += 3   # run-length record: u16 count, one byte
    return out


def write_nso(path, orig, m):
    """m as an uncompressed NSO: the original header with its flags cleared (no compression, no hash checks) and the segments stored one after another"""
    h = bytearray(orig[:0x100]); struct.pack_into('<I', h, 0xc, 0)
    at = 0x100
    for k, (mo, sz) in enumerate(m.segments):
        struct.pack_into('<II', h, 0x10 + k * 0x10, at, mo); struct.pack_into('<I', h, 0x60 + 4 * k, sz); at += sz
    with open(path, 'wb') as f:
        f.write(h)
        for mo, sz in m.segments: f.write(m.image[mo:mo + sz])


def patches_for(mod, build_id):
    """the mod's IPS files for this build ID: Atmosphère names them by the build ID's hex digits, trailing zeros may be dropped"""
    bid = build_id.hex().upper()
    out = []
    for p in sorted(list((mod / 'exefs').glob('*.ips')) + list((mod / 'exefs_patches').glob('*/*.ips'))):
        stem = p.stem.upper()
        if re.fullmatch(r'[0-9A-F]{1,64}', stem) and bid[:len(stem)] == stem: out.append(p)
    return out


def apply(ex, mod, out):
    ex, mod, out = Path(ex), Path(mod), Path(out)
    if not (mod / 'exefs').is_dir() and not (mod / 'romfs').is_dir(): sys.exit(f'[RED] {mod}: no exefs or romfs folder (an Atmosphère mod has atmosphere/contents/<title ID>/exefs and romfs; give that folder)')
    (out / 'ExeFS').mkdir(parents=True, exist_ok=True)
    base = {p.name for p in (ex / 'ExeFS').iterdir() if p.is_file()}
    added = {p.name for p in (mod / 'exefs').iterdir() if p.name in ORDER and is_nso(p)} if (mod / 'exefs').is_dir() else set()
    for name in sorted(base | added):
        src = (mod / 'exefs' / name) if name in added else (ex / 'ExeFS' / name)
        dst = out / 'ExeFS' / name
        if name not in ORDER or not is_nso(src):
            if name == 'main.npdm' and (mod / 'exefs' / name).is_file(): src = mod / 'exefs' / name
            shutil.copyfile(src, dst); continue
        raw = src.read_bytes(); m = nso.load(raw, str(src))
        ips = patches_for(mod, m.build_id[:0x20])
        for p in ips:
            for off, b in ips_records(p.read_bytes(), str(p)):
                o = off - 0x100
                if o < 0 or o + len(b) > len(m.image): sys.exit(f'[RED] {p}: a record at file offset {off:#x} is outside {name}\'s image ({len(m.image):#x} bytes)')
                m.image[o:o + len(b)] = b
            print(f'# {name}: {p.name} applied', file=sys.stderr)
        if ips or name in added: write_nso(dst, raw, m)
        else: shutil.copyfile(src, dst)
    for f in ('control.nacp', 'icon.jpg'):
        if (ex / f).is_file(): shutil.copyfile(ex / f, out / f)
    rom = ex / 'RomFS.img' if (ex / 'RomFS.img').is_file() else ex / 'RomFS'   # an image (the NSP script's extraction) or a folder
    if (mod / 'romfs').is_dir(): n = romfs_image.pack_layers(rom, mod / 'romfs', out / 'RomFS.img')
    elif rom.is_file(): n = None; shutil.copyfile(rom, out / 'RomFS.img')
    else: n = romfs_image.pack(rom, out / 'RomFS.img')
    # every module's place in Horizon's layout: an added module goes at its offset from main
    mods = [n_ for n_ in ORDER if n_ in base | added and is_nso(out / 'ExeFS' / n_)]
    at, off = {}, 0
    for name in mods:
        m = nso.read(out / 'ExeFS' / name)
        if name in added and name not in base: at[name] = off
        off += (m.segments[2][0] + m.segments[2][1] + m.bss + PAGE - 1) & ~(PAGE - 1)
    print(f'# RomFS: {n} entries after merging {mod / "romfs"}' if n is not None else '# RomFS: unchanged', file=sys.stderr)
    return mods, at


if __name__ == '__main__':
    if len(sys.argv) != 4: sys.exit(__doc__ or 'usage: mod_apply.py <extraction> <mod folder> <out extraction>')
    mods, at = apply(*sys.argv[1:])
    print('modules\t' + ' '.join(mods))
    if at: print('module_at\t' + ' '.join(f'{k}={v:#x}' for k, v in at.items()))
