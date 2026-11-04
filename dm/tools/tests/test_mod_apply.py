"""Atmosphère-layout mods (mod_apply.py): IPS patches by build ID, added modules at their Horizon offsets, LayeredFS-style RomFS merging (romfs_image.pack_layers)."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / 'dm/tools')]
import mod_apply
import nso
import romfs_image


def make_nso(path, build_id, text=0x2000, ro=0x1000, data=0x1000, bss=0x3000, fill=b'\x1f\x20\x03\xd5'):
    """an uncompressed NSO: text filled with nop, ro and data zero"""
    h = bytearray(0x100); h[:4] = b'NSO0'
    at, mo = 0x100, 0
    for k, sz in enumerate((text, ro, data)):
        struct.pack_into('<III', h, 0x10 + k * 0x10, at, mo, sz); struct.pack_into('<I', h, 0x60 + 4 * k, sz); at += sz; mo += sz
    struct.pack_into('<I', h, 0x3c, bss); h[0x40:0x40 + len(build_id)] = build_id
    path.write_bytes(bytes(h) + fill * (text // 4) + bytes(ro + data))


def ips32(records):
    return b'IPS32' + b''.join(o.to_bytes(4, 'big') + len(b).to_bytes(2, 'big') + b for o, b in records) + b'EEOF'


class ModApply(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        r = Path(self.tmp.name)
        self.ex, self.mod, self.out = r / 'ex', r / 'mod', r / 'out'
        (self.ex / 'ExeFS').mkdir(parents=True); (self.mod / 'exefs').mkdir(parents=True)
        self.main_id = bytes.fromhex('94ceae325c205c4b9d6f7235552f28fd')
        make_nso(self.ex / 'ExeFS/main', self.main_id)
        make_nso(self.ex / 'ExeFS/subsdk0', b'\x11' * 16, text=0x1000, bss=0x800)
        make_nso(self.ex / 'ExeFS/sdk', b'\x22' * 16)
        (self.ex / 'ExeFS/main.npdm').write_bytes(b'META')
        make_nso(self.mod / 'exefs/subsdk1', b'\x33' * 16, text=0x1000)
        (self.mod / 'exefs' / (self.main_id.hex().upper() + '.ips')).write_bytes(ips32([(0x100 + 0x40, b'\x00\x00\x00\x94'), (0x100 + 0x2000, b'RO')]))
        (self.mod / 'exefs/0123456789ABCDEF.ips').write_bytes(ips32([(0x100, b'\xff\xff\xff\xff')]))   # another build's patch: not applied
        rom = r / 'romfs'; (rom / 'Data/a').mkdir(parents=True)
        (rom / 'Data/a/keep').write_bytes(b'base keep'); (rom / 'Data/a/swap').write_bytes(b'base swap'); (rom / 'top').write_bytes(b'top')
        romfs_image.pack(rom, self.ex / 'RomFS.img')
        (self.mod / 'romfs/Data/a').mkdir(parents=True); (self.mod / 'romfs/Data/b').mkdir(parents=True)
        (self.mod / 'romfs/Data/a/swap').write_bytes(b'mod swap'); (self.mod / 'romfs/Data/b/new').write_bytes(b'mod new')

    def test_patches_modules_and_layout(self):
        mods, at = mod_apply.apply(self.ex, self.mod, self.out)
        self.assertEqual(mods, ['main', 'subsdk0', 'subsdk1', 'sdk'])
        # Horizon's layout: main (0x4000 image + 0x3000 bss), then subsdk0 (0x3000 + 0x800 → 0x4000 rounded to a page)
        self.assertEqual(at, {'subsdk1': 0x7000 + 0x4000})
        m = nso.read(self.out / 'ExeFS/main')
        self.assertEqual(m.build_id[:16], self.main_id)
        self.assertEqual(bytes(m.image[0x40:0x44]), b'\x00\x00\x00\x94')
        self.assertEqual(bytes(m.image[0x2000:0x2002]), b'RO')
        self.assertEqual(bytes(m.image[:4]), b'\x1f\x20\x03\xd5', 'a patch for another build ID is not applied')
        self.assertEqual(nso.read(self.out / 'ExeFS/subsdk1').build_id[:16], b'\x33' * 16)
        self.assertEqual((self.out / 'ExeFS/sdk').read_bytes(), (self.ex / 'ExeFS/sdk').read_bytes(), 'an unpatched module is copied as it is')
        self.assertEqual((self.out / 'ExeFS/main.npdm').read_bytes(), b'META')

    def test_romfs_layers(self):
        mod_apply.apply(self.ex, self.mod, self.out)
        img = self.out / 'RomFS.img'
        idx = romfs_image.read_index(img)
        def read(p):
            _, o, n = idx[p]
            with open(img, 'rb') as f: f.seek(o); return f.read(n)
        self.assertEqual(read('Data/a/keep'), b'base keep')
        self.assertEqual(read('Data/a/swap'), b'mod swap')
        self.assertEqual(read('Data/b/new'), b'mod new')
        self.assertEqual(read('top'), b'top')
        self.assertTrue(idx['Data/b'][0])

    def test_ips_outside_the_image_stops(self):
        (self.mod / 'exefs' / (self.main_id.hex().upper() + '.ips')).write_bytes(ips32([(0x100 + 0x10000, b'xx')]))
        with self.assertRaises(SystemExit): mod_apply.apply(self.ex, self.mod, self.out)


if __name__ == '__main__':
    unittest.main()
