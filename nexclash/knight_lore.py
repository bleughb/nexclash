"""Knight Lore (Ultimate, 1984; 48K): the Enhanced masked colour renderer, and the original game with a whole Sinclair
alt ROM for the default. games/knight_lore.md has the design and results.

The Enhanced set's painted figure pages and room floors (ASSETS: page-*.bin, floor-selector.bin) come from the Spec256
conversion's art and are private reference inputs, never in this repository; the pilot run's work/build_assets.py
makes them from the approved PNGs and the user's own copy of the game.

    python -m nexclash.knight_lore SNAPSHOT ASSETS OUT.nex            the Enhanced build
    python -m nexclash.knight_lore SNAPSHOT - OUT.nex --original      the default: the original game, whole alt ROM
"""
import json, sys
from pathlib import Path
from .build import rom48

ROOT = Path(__file__).resolve().parents[1]

class KnightLorePatch:
    name='Knight Lore masked colour renderer'
    def __init__(self, assets, enhanced=True):
        self.assets=Path(assets); self.enhanced=enhanced
        p=json.loads((ROOT/'docs/profiles/knight_lore.json').read_text())
        self.syms={k:int(v,16)for k,v in p['hooks']['syms'].items()}
        self.rom_code=bytes.fromhex(p['hooks']['rom'])
        self.setup_code=bytes.fromhex(p['hooks']['setup'])
        self.regblock=0x2000+len(self.rom_code)
        self.slot1=(24,self.regblock);self.altrom=(0x2000,self.regblock+20)
        page=bytearray(rom48()[8192:]);page[:len(self.rom_code)]=self.rom_code;page[0x1F00:0x2000]=(self.assets/'floor-selector.bin').read_bytes();self.page=bytes(page)
        self.setup_call=0xD000;self.stub_extra=self.setup_code;self.hook_page_data=b''
        self.uses_printer_buffer=False;self.keep_printer_buffer=True;self.tail_addr=0x5B00;self.max_tail=128
        self.sites=[]
        for a,hx,s in [(0xD71B,'dd7e1a','h_plot'),(0xC515,'112000','h_clear'),(0xD567,'010018','h_fullclear'),(0xD544,'210040','h_hide'),(0xB01E,'cd9fd5','h_render'),(0xB06E,'cd6fd5','h_fullcopy'),(0xB035,'210005','h_delay'),(0xAFBD,'3aa25b','h_actor_open'),(0xBA22,'3ac35b','h_actor_cancel_gameover'),(0xAF7F,'21a85b','h_actor_cancel_newgame')]:
            self.sites.append((a,bytes.fromhex(hx),b'\xcd'+self.syms[s].to_bytes(2,'little')))
        for row in json.loads((ROOT/'docs/profiles/knight_lore_sound_sites.json').read_text())['sites']:
            a=row['pc'];target=row['target'];opcode=0xC4 if row['op'].startswith('CALL NZ,')else 0xFC if row['op'].startswith('CALL M,')else 0xCD
            self.sites.append((a,bytes([opcode])+target.to_bytes(2,'little'),bytes([opcode])+self.syms[row['label']].to_bytes(2,'little')))
        pages={24:self.page,25:bytes(8192),26:self.page,27:bytes(8192)}
        for f in self.assets.glob('page-*.bin'):pages[int(f.stem[5:])]=f.read_bytes()
        banks={}
        for pg,data in pages.items():
            bank=banks.setdefault(pg//2,bytearray(16384));bank[(pg&1)*8192:((pg&1)+1)*8192]=data
        self.extra_banks={b:bytes(d)for b,d in banks.items()}
    def apply(self,snap):
        assert not snap.is128
        ram=bytearray(snap.banks[5]+snap.banks[2]+snap.banks[0])
        for a,old,new in self.sites:
            actual=bytes(ram[a-16384:a-16384+len(old)])
            if actual!=old:raise ValueError(f'{a:04X}: {actual.hex()} != {old.hex()}')
            ram[a-16384:a-16384+len(new)]=new
        snap.banks[5],snap.banks[2],snap.banks[0]=bytes(ram[:16384]),bytes(ram[16384:32768]),bytes(ram[32768:])
        restore_tail(self,snap)

class KnightLoreOriginal:
    """Original game bytes with a complete Sinclair ROM on NextZXOS26.11."""
    name='Knight Lore original presentation'
    def __init__(self):
        self.page=bytes(rom48()[8192:]);self.slot1=(24,0x3C00);self.altrom=(0x3C00,0x3C14)
        self.setup_call=None;self.stub_extra=b'';self.hook_page_data=b''
        self.uses_printer_buffer=False;self.keep_printer_buffer=True;self.tail_addr=0x5B00;self.max_tail=128
        self.extra_banks={12:self.page+bytes(8192)}
    def apply(self,snap):
        if snap.is128:raise ValueError('Knight Lore expected48K release')
        restore_tail(self,snap)


def restore_tail(p,snap):
    """Erase the temporary RAM tail and restore exact entry registers/R."""
    from . import z80tonex as Z
    backup,entry=0x3900,0x3940
    tail,_,restore,_=Z.build_tail(snap,p.tail_addr,p.slot1,True)
    if len(tail)>64:raise ValueError('tail backup capacity')
    original=bytes(snap.read(p.tail_addr+i)for i in range(len(tail)))
    code=b'\xF3\x21'+Z.w16(backup)+b'\x11'+Z.w16(p.tail_addr)+b'\x01'+Z.w16(len(tail))+b'\xED\xB0'+tail[restore:]
    if entry+len(code)>=0x3A00:raise ValueError('tail restorer capacity')
    assert set(rom48()[backup:entry+len(code)])=={255}
    page=bytearray(p.page);page[backup-8192:backup-8192+len(original)]=original
    page[entry-8192:entry-8192+len(code)]=code;p.page=bytes(page)
    p.extra_banks[12]=p.page+p.extra_banks[12][8192:]
    p.altrom=(min(backup,p.altrom[0]),p.altrom[1])
    p.original_pc=snap.pc;p.tail_restore_bytes=len(tail);snap.pc=entry


def main(argv=None):
    from . import z80tonex as Z
    a = list(sys.argv[1:] if argv is None else argv)
    original = '--original' in a
    a = [x for x in a if x != '--original']
    if len(a) != 3: raise SystemExit(__doc__)
    snapshot, assets, out = a
    patch = KnightLoreOriginal() if original else KnightLorePatch(assets)
    Z.convert(snapshot, out, patch=patch, quiet=True)


if __name__ == '__main__':
    main()
