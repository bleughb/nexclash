"""Knight Lore (Ultimate, 1984; 48K): the Enhanced masked colour renderer, and the original game with a whole Sinclair
alt ROM for the default. games/knight_lore.md has the design and results.

The Enhanced set's painted figure pages and room floors (ASSETS: page-*.bin, floor-selector.bin) come from the Spec256
conversion's art and are private reference inputs, never in this repository; the pilot run's work/build_assets.py
makes them from the approved PNGs and the user's own copy of the game.

    python -m nexclash.knight_lore SNAPSHOT ASSETS OUT.nex            the Enhanced build
    python -m nexclash.knight_lore SNAPSHOT - OUT.nex --original      the default: the original game, whole alt ROM

`nexclash.py auto` (nexclash/engines.py: is_knight_lore) builds the default only, GAME.nex, and boots it; the Enhanced
set needs the private ASSETS, so it is built with the command above.
"""
import json, sys
from pathlib import Path
from .build import rom48

ROOT = Path(__file__).resolve().parents[1]
from .hooklib import CMP_R as CMP     # the pilot's replay compared every register, R included

def load_profile():
    return json.loads((ROOT/'docs/profiles/knight_lore.json').read_text())


def is_knight_lore(snap):
    """48K snapshot with Knight Lore's actor-update entry at the profile's signature address."""
    ram=bytes(snap.ram(-1))
    if len(ram)!=49152:
        return False
    s=load_profile()['signature']
    want=bytes.fromhex(s['hex'])
    return ram[s['addr']-16384:s['addr']-16384+len(want)]==want


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


def boot_problems(nex, z80, patch):
    """Boot NEX (as the converter's loader and as NEXLOAD leaves the machine) to the game's own entry, after the tail
    restorer: every register including R, and RAM 0x4000-0xFFFF, must equal the snapshot after patch.apply."""
    from . import z80tonex as Z, nextboot
    import copy
    s=Z.Z80Snapshot(z80);q=copy.deepcopy(patch);q.apply(s)
    ram=s.banks[5]+s.banks[2]+s.banks[0]
    bad=[]
    for nexload in (False,True):
        st=nextboot.boot(nex,q.original_pc,nexload=nexload);R=st['R'];w=lambda n:R[n]*256+R[n+1]
        bad+=[('nexload' if nexload else 'loader',)+tuple(x) for x in st['bad']]
        for k,v in ((0,s.a),(1,s.f),(12,s.sp),(14,s.i),(15,s.r),(26,s.iff1),(27,s.im)):
            if R[k]!=v:bad.append(('register',k,R[k],v))
        for k,v in ((2,s.bc),(4,s.de),(6,s.hl),(8,s.ix),(10,s.iy),(16,s.a_*256+s.f_),(18,s.bc_),(20,s.de_),(22,s.hl_)):
            if w(k)!=v:bad.append(('register',k,w(k),v))
        diff=[a for a in range(0x4000,0x10000) if st['mem'][a]!=ram[a-0x4000]]
        if diff:bad.append(('RAM differs',len(diff),diff[:6]))
    return bad


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Not an RZX verifier yet: Knight Lore's proof is the pilot run's replay oracle, soaks and negatives
    (games/knight_lore.md "Evidence"). Porting that harness is the open item; until then this says so."""
    raise NotImplementedError('knight_lore: no RZX verifier yet (games/knight_lore.md "Evidence")')


def unit_tests(patch, states, neg=None):
    """No unit tests in the engine yet: the ABI, wrapper, compositor and negative cases ran in the pilot run
    (games/knight_lore.md "Evidence")."""
    raise NotImplementedError('knight_lore: no unit tests yet (games/knight_lore.md "Evidence")')


def auto(a, z80, name, out, say):
    """nexclash.py auto: the default build (the original game, whole Sinclair alt ROM, tail restored) and its boot
    check. Knight Lore has no clash to fix; the Enhanced set needs private ASSETS (module docstring)."""
    import hashlib, os
    from . import z80tonex as Z
    say('Game      : %s' % name)
    say('Engine    : knight_lore (default: original game, whole alt ROM; Enhanced needs private ASSETS: python -m nexclash.knight_lore)')
    nex=os.path.join(out,name+'.nex')
    patch=KnightLoreOriginal()
    Z.convert(z80,nex,patch=patch,quiet=True)
    bad=boot_problems(nex,z80,KnightLoreOriginal())
    say('Default   : %s  %s  tail %d bytes restored' % (os.path.basename(nex),hashlib.md5(open(nex,'rb').read()).hexdigest(),patch.tail_restore_bytes))
    say('Boot      : %s' % ('OK (registers with R, RAM; converter loader and NEXLOAD)' if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    say('Result    : %s' % ('PASSED' if not bad else 'FAILED'))
    return not bad


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
