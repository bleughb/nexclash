"""Martianoids (Ultimate Play The Game, 1987, 48K): original presentation.

The play area is monochrome in the original game. This engine preserves its
ordered mask/XOR renderer and does not claim an attribute-clash improvement
where none exists. The sound-free render span is accelerated and paced; a
separate optional colour set uses the approved, owner-edited painting sheet.
"""
from pathlib import Path
from collections import Counter
import hashlib,json
from . import hooklib,simpool,z80tonex as zt

ROOT=Path(__file__).resolve().parents[1]
PROFILE=ROOT/'docs/profiles/martianoids.json'
SOURCE_MD5='5df07fbd5dabdcb9a909b86cf690a4e8'
TAPE_SHA256='bb1b10f3281755e4fa3376009c23fa4b87fb058f241b76d30eaa9efd0d59b528'
CMP=tuple(hooklib.CMP_R)
SITES={0x99EF:(0xBF22,'h_open'),0x99FE:(0xA739,'h_close')}
ENHANCED_SITES={0x98D6:(0xB1A3,'h_hide'),0xB217:(0xB1C2,'h_hide_view14'),0xB212:(0xB1D6,'h_hide_view20')}
DECISIONS={'figures':'original mask/XOR pixels and monochrome colours',
           'scenery':'original checker floor, geometry and HUD',
           'pace':'original; shared hlib_pace limiter','outline':'none','enhanced':'approved owner-edited colours; off by default'}

def _profile_path():
    return PROFILE

def load_profile():
    return json.loads(PROFILE.read_text())

def _peek(snap):
    banks=getattr(getattr(snap,'memory',None),'banks',None) or getattr(snap,'banks',None)
    if banks is not None:return lambda a:banks[{1:5,2:2,3:0}[a>>14]][a&16383]
    ram=snap.ram(-1)
    return lambda a:ram[a-16384]

def is_martianoids(snap):
    if getattr(snap,'machine','48K')!='48K' or getattr(snap,'is128',False):return False
    try:
        peek=_peek(snap)
        checks={0x9601:bytes.fromhex('f3310060ed56'),0xB2BC:bytes.fromhex('dd7e00876f260001a360'),
                **{a:b'\xcd'+zt.w16(body) for a,(body,_) in SITES.items()}}
        return all(bytes(peek(a+k) for k in range(len(v)))==v for a,v in checks.items())
    except (AttributeError,KeyError,TypeError,IndexError):return False

class Patch:
    name='Martianoids: original presentation and original pace'
    uses_printer_buffer=False
    tail_addr=0x5B00
    max_tail=128
    hook_page_data=b''
    setup_call=0xD000
    def __init__(self,source=None,enabled=True,enhanced=False,colours=None):
        self.source=str(source) if source else None
        self.enhanced=bool(enhanced);self.enabled=enabled;self.art=None;self.loading_screen=None
        if source:
            tape=Path(source).with_suffix('.tap')
            if tape.exists() and hashlib.sha256(tape.read_bytes()).hexdigest()==TAPE_SHA256:
                # Original turbo block: flag + 6912 screen bytes + loader trailer.
                self.loading_screen=tape.read_bytes()[269:269+6912]
        h=load_profile()['hooks'];self.syms={k:int(v,16) for k,v in h['syms'].items()}
        self.code=bytes.fromhex(h['rom']);self.stub_extra=bytes.fromhex(h['setup'])
        self.slot1=(25,self.syms['regblock'])
        self.altrom=self.altrom0=(0x2800,0x3D00)
        from .build import rom48
        self.ram=bytearray(rom48()[0x2000:0x4000]);self.ram[0x800:0x800+len(self.code)]=self.code
        self.ram[0x1E00:0x1F00]=bytes(256)
        self.ram[0x1900:0x1A00]=bytes(256)
        self.site_targets=dict(SITES)
        if enabled and source:
            from . import martianoids_art as art
            if not source:raise ValueError('Enhanced requires its original snapshot source')
            snap=zt.Z80Snapshot(str(source));mem=bytes(16384)+snap.banks[5]+snap.banks[2]+snap.banks[0]
            self.art=art.compile(mem,colours);self.ram[art.DIRECTORY-0x2000:art.DIRECTORY-0x2000+2048]=self.art['directory']
            self.ram[0x1D00:0x1D20]=self.art['palette']
        if enhanced:
            if not self.art:raise ValueError('Enhanced requires its original snapshot source')
            self.ram[0x1E34]=1
            stub=bytearray(self.stub_extra);stub[self.syms['setup_enhanced']-self.setup_call+1]=1;self.stub_extra=bytes(stub)
            self.site_targets.update(ENHANCED_SITES)
        self.sites=[(a,b'\xcd'+zt.w16(body),b'\xcd'+zt.w16(self.syms[name])) for a,(body,name) in self.site_targets.items()] if enabled else []
        self._banks()
    def _banks(self):
        # The generic loader copies page 25 into hidden ROM. Keep only tiny
        # entry/return veneers there: BASIC still uses the calculator ROM before
        # USR starts the game. All code/data and writable state live in page 24.
        from .build import rom48
        self.page=bytearray(rom48()[0x2000:0x4000])
        for name in ('h_open','h_close','h_hide','h_hide_view14','h_hide_view20','boot_resume'):
            at=self.syms[name]-0x2000;n=5 if name=='boot_resume' else 4
            self.page[at:at+n]=self.ram[at:at+n]
        for i in range(len(self.code)-4):
            if self.code[i:i+4]==bytes.fromhex('ed9151ff'):
                at=0x800+i+4;n=4 if at==self.syms['boot_iff']-0x2000 else 3
                self.page[at:at+n]=self.ram[at:at+n]
        pages=dict(self.art['pages']) if self.art else {};pages[24]=bytes(self.ram);pages[25]=bytes(self.page)
        self.extra_banks={b:pages.get(2*b,bytes(8192))+pages.get(2*b+1,bytes(8192)) for b in {p//2 for p in pages}}
    def apply(self,snap):
        if not is_martianoids(snap):raise ValueError('Not the supported Martianoids 48K release')
        self.ram[0x1C00:0x1D00]=snap.banks[5][0x1B00:0x1C00]
        for name,value,width in [('boot_r',((snap.r-6)&127)|(snap.r&128),1),('boot_sp',snap.sp,2),('boot_jump',snap.pc,2)]:
            o=self.syms[name]-0x2000+1;self.ram[o:o+width]=value.to_bytes(width,'little')
        self.ram[self.syms['boot_iff']-0x2000]=0xFB if snap.iff1 else 0xF3
        ram=bytearray(snap.banks[5]+snap.banks[2]+snap.banks[0])
        restore=bytearray()
        if self.loading_screen is not None:
            for i,(old,new) in enumerate(zip(ram[:6912],self.loading_screen)):
                if old!=new:restore+=zt.w16(0x4000+i)+bytes([old])
            if len(restore)+2>256:raise ValueError('Loading screen restoration exceeds its reserved table')
            ram[:6912]=self.loading_screen
        restore+=b'\0\0';self.ram[0x1900:0x1900+len(restore)]=restore
        self._banks()
        for a,old,new in self.sites:
            if ram[a-0x4000:a-0x4000+len(old)]!=old:raise ValueError('Original bytes differ at '+hex(a))
            ram[a-0x4000:a-0x4000+len(new)]=new
        snap.banks[5],snap.banks[2],snap.banks[0]=bytes(ram[:16384]),bytes(ram[16384:32768]),bytes(ram[32768:])
        snap.pc=self.syms['boot_resume']

def build(source,destination,enabled=True,enhanced=False):
    p=Patch(source,enabled,enhanced);zt.convert(str(source),str(destination),patch=p,quiet=True);return p

class View:
    def __init__(self,mem,patch=None,page=None,pages=None):
        self.mem=bytearray(mem);self.patch=patch;self.page=bytearray(page if page is not None else patch.ram if patch else bytes(8192));self.model=None
        self.pages=pages if pages is not None else {k:bytearray(v) for k,v in patch.art['pages'].items()} if patch and patch.art else {}
        self.dirty=set()
        if patch:
            for a,old,new in patch.sites:self.mem[a:a+len(new)]=new
    def __len__(self):return 65536
    def __getitem__(self,a):
        if isinstance(a,slice):return bytes(self[i] for i in range(*a.indices(65536)))
        mapped=self.model.nr.get(0x50+(a>>13),[255,255,10,11,4,5,0,1][a>>13]) if self.model else 255
        if self.patch and 0x2000<=a<0x4000:
            if mapped==24:return self.page[a-0x2000]
            if 0x2800<=a<0x3D00:return self.patch.page[a-0x2000]
        if mapped in self.pages:return self.pages[mapped][a&8191]
        if mapped in (10,11,4,5,0,1):return self.mem[{10:0x4000,11:0x6000,4:0x8000,5:0xA000,0:0xC000,1:0xE000}[mapped]+(a&8191)]
        return self.mem[a]
    def __setitem__(self,a,v):
        if self.patch and 0x2000<=a<0x4000 and self.model.nr.get(0x51,255)==24:self.page[a-0x2000]=v
        else:
            mapped=self.model.nr.get(0x50+(a>>13),[255,255,10,11,4,5,0,1][a>>13]) if self.model else 255
            if mapped in self.pages:self.pages[mapped][a&8191]=v
            elif mapped in (10,11,4,5,0,1):
                actual={10:0x4000,11:0x6000,4:0x8000,5:0xA000,0:0xC000,1:0xE000}[mapped]+(a&8191)
                self.mem[actual]=v;self.dirty.add(actual)
            elif a>=0x4000:self.mem[a]=v;self.dirty.add(a)

class Model(hooklib.NextModel):
    def __init__(self,sim,speed=0):
        super().__init__(sim,speed);self.nr.update({0x50+i:p for i,p in enumerate([255,255,10,11,4,5,0,1])});self.nr[1]=0x32;self.io=[]
    def write_port(self,regs,port,v,*args):
        if port in (0x243B,0x253B) or port&255==0x6B:return super().write_port(regs,port,v,*args)
        self.io.append((port,v))

def run_hook(mem,regs,patch,page=None,speed=0,real=0,pages=None,nr=None):
    """Execute just the hook prelude to the original CALL target, preserving its SP."""
    from .dizzy6 import _rw_simulator
    Simulator=_rw_simulator()
    v=View(mem,patch,page,pages);s=simpool.machine(Simulator,v,list(regs),'martianoids-hook')
    model=Model(s,speed);model.real=real;v.model=model
    if nr:model.nr.update(nr)
    target=patch.site_targets[regs[24]][0];n=0
    while n==0 or s.registers[24]!=target:
        s.opcodes[v[s.registers[24]]]()
        n+=1
        if n>2000000:raise AssertionError('hook did not terminate')
    return list(s.registers),v,model

def verify(patch,rzx_path,stop=None,collect=0,progress=None):
    """Induction at every changed CALL: exact original body entry and all 48K RAM.

    Both hooks finish BEFORE the displaced, unchanged original routine. Matching
    its complete entry state proves its subsequent original instructions; the
    next changed CALL starts the following induction step. Hook RAM persists.
    Native timing and I/O checks are separate from this semantic replay.
    """
    from collections import defaultdict
    from skoolkit.simulator import Simulator
    c=Counter();examples=defaultdict(list);states=[];page=bytearray(patch.ram);pages=None;nr=None
    if patch.enhanced:
        from .martianoids_art import expected_canvas,load_colours
        colours=load_colours()
    sites={a+k:v for a,old,new in patch.sites for k,v in enumerate(new)}
    originals={a+k:v for a,old,new in patch.sites for k,v in enumerate(old)}
    opened=None;speed=0
    def fail(key,detail):
        c[key+'!']+=1
        if len(examples[key])<5:examples[key].append(detail)
    def on_pc(pc,sim,frame,fetch):
        nonlocal page,pages,nr,opened,speed
        if pc not in patch.site_targets:
            fail('jump into changed instruction',{'pc':pc,'frame':frame});return
        regs=list(sim.registers);mem=bytes(sim.memory)
        if collect and sum(x[0]==pc for x in states)<collect:states.append((pc,regs,mem))
        for a,v in originals.items():
            if mem[a]!=v:fail('original changed patch bytes',{'pc':pc,'address':a,'value':mem[a]})
        # The original CALL alone defines the unchanged body's exact entry.
        ref=simpool.machine(Simulator,list(mem),regs,'martianoids-original-call');ref.opcodes[mem[pc]]()
        elapsed=0 if opened is None else max(0,(frame-opened[0])*69888+regs[25]-opened[1])
        got,view,model=run_hook(mem,regs,patch,page,speed,elapsed/8 if pc==0x99FE else 0,pages,nr)
        for i in CMP:
            # The C simulator represents IFF true as 255, Python as 1.
            if (bool(ref.registers[i])!=bool(got[i])) if i==26 else (ref.registers[i]!=got[i]):
                fail('registers differ',{'pc':pc,'frame':frame,'register':i,'original':ref.registers[i],'patched':got[i]})
        expected=bytearray(ref.memory[0x4000:])
        for a,v in sites.items():expected[a-0x4000]=v
        actual=view.mem[0x4000:]
        if actual!=expected:
            bad=[a+0x4000 for a,(x,y) in enumerate(zip(expected,actual)) if x!=y]
            fail('48K RAM differs',{'pc':pc,'frame':frame,'count':len(bad),'addresses':bad[:8]})
        if model.nr[0x51]!=255:fail('MMU not restored',{'pc':pc,'value':model.nr[0x51]})
        if model.io:fail('extra game I/O',{'pc':pc,'io':model.io[:4]})
        if pc==0x99EF:
            if opened is not None:fail('nested render window',{'frame':frame})
            opened=(frame,regs[25]);want_speed=3
        elif pc==0x99FE:
            if opened is None:fail('close without render window',{'frame':frame})
            opened=None;want_speed=0;c['complete render windows']+=1
            if patch.enhanced:
                want=expected_canvas(mem,colours);base=model.nr[0x12]*2;picture=b''.join(view.pages[base+k] for k in range(6))
                if picture!=want:
                    bad=[i for i,(x,y) in enumerate(zip(want,picture)) if x!=y]
                    fail('ordered colour canvas differs',{'frame':frame,'pixels':len(bad),'examples':bad[:8]})
                c['complete colour canvases']+=1;c['colour pixels compared']+=49152
        else:
            want_speed=speed;c['menu resets']+=1
            if model.nr.get(0x69)!=0:fail('colour remains on at menu reset',{'frame':frame})
        if model.nr[7]!=want_speed:fail('clock differs',{'pc':pc,'value':model.nr[7],'wanted':want_speed})
        page=view.page;pages=view.pages;nr=dict(model.nr);speed=model.nr[7];c['hooks']+=1;c['48K bytes compared']+=49152;c['R comparisons']+=1
        if progress and c['hooks']%500==0:progress(frame,c)
    c['frames'],error=trace(rzx_path,set(patch.site_targets)|{a+k for a in patch.site_targets for k in (1,2)},on_pc,stop)
    if error:fail('recording desynced',error)
    if opened is not None:c['unfinished render window at recording end']+=1
    return (c,dict(examples),states) if collect else (c,dict(examples))

def trace(rzx_path,pcs,on_pc,stop=None):
    """Bounded C-simulator recording trace, using the shared probe's hook protocol."""
    import skoolkit.rzxplay as rp
    from skoolkit import SkoolKitError
    from skoolkit.snapshot import Snapshot
    from types import SimpleNamespace
    blocks=rp.parse_rzx(str(rzx_path))
    while blocks and isinstance(blocks[-1].obj,Snapshot):blocks.pop()
    ctx=rp.RZXContext(None)
    ctx.total_frames=sum(len(b.obj.frames) for b in blocks if isinstance(b.obj,rp.InputRecording))
    if stop:ctx.total_frames=min(stop,ctx.total_frames)
    class Sink:
        def write(self,s):pass
    ctx.tracefile=Sink();wanted=frozenset(pcs)
    def visit(tf,c,fc,pc):
        if pc in wanted:on_pc(pc,c.simulator,c.frame_count,fc)
    old=rp.trace_exec;rp.trace_exec=visit;error=None
    try:
        opts=SimpleNamespace(cmio=False,python=False,quiet=True,stop=stop or 0,force=False)
        while blocks:
            rp.process_block(blocks.pop(0).obj,opts,0,ctx)
            if ctx.stop:break
    except SkoolKitError as e:error=str(e)
    finally:rp.trace_exec=old
    return ctx.frame_count,error

from .martianoids_art import COLOURS,load_colours,colour_identity
RECOLOUR={'game':'martianoids','output':'sprites','colours':'docs/profiles/martianoids_colours.json','clear':False,
          'note':'Original drawn pixels only; exact opaque black and original XOR effects. Enhanced is optional and off by default.'}

def recolour(nex_bytes,cmap):
    """Rewrite only compiled colour-source pages; game RAM and geometry are fixed."""
    from . import recolour as RC,martianoids_art as art
    banks=RC.banks(nex_bytes);peek=RC.nex_peek(nex_bytes);p=Patch()
    if not {0,2,5,12,46,47}<=set(banks):raise ValueError('Not a Martianoids build with colour assets')
    hook=banks[12][:8192]
    if hook[0x1E34] not in (0,1):raise ValueError('Unexpected Enhanced selector')
    targets=dict(SITES)
    if hook[0x1E34]:targets.update(ENHANCED_SITES)
    for a,(body,name) in targets.items():
        if bytes(peek(a+k) for k in range(3))!=b'\xcd'+zt.w16(p.syms[name]):raise ValueError('Martianoids patch site differs at '+hex(a))
    skip={p.syms[name]-0x2800+k for name,n in [('boot_r',1),('boot_sp',2),('boot_jump',2)] for k in range(1,n+1)}|{p.syms['boot_iff']-0x2800}
    end=p.syms['rom_end']-0x2800
    if any(hook[0x800+i]!=p.code[i] for i in range(end) if i not in skip):raise ValueError('Martianoids runtime differs; rebuild first')
    if art.colour_identity(peek)['graphics_sha256']!=art.GRAPHICS_SHA256:raise ValueError('Original graphics differ from the supported release')
    compiled=art.compile(bytes(peek(a) for a in range(65536)),cmap)
    if hook[art.DIRECTORY-0x2000:art.DIRECTORY-0x2000+2048]!=compiled['directory']:raise ValueError('Graphics directory differs')
    new={}
    for page,data in compiled['pages'].items():
        if page<art.FIRST_SOURCE_PAGE:continue
        bank=page//2
        if bank not in banks:raise ValueError('Colour source bank missing')
        block=bytearray(new.get(bank,banks[bank]));off=(page&1)*8192;block[off:off+8192]=data;new[bank]=bytes(block)
    result,changed=RC.splice(nex_bytes,new)
    return result,{'banks changed':changed,'map entries used':len(cmap),'map entries ignored':0,'renderer':'ordered Layer 2 canvas','enhanced':bool(hook[0x1E34])}

def sheets(source,out,name='MARTIANOIDS',colours=None):
    """Write NEW standard sheets; never overwrite an owner's existing painting."""
    from . import coloursheet as CS,martianoids_art as art
    from PIL import Image
    out=Path(out);out.mkdir(parents=True,exist_ok=True);png=out/(name+'_PAINTING_SPRITES.png')
    if png.exists():raise FileExistsError('Painting already exists; preserve it and use recolour to import edits: '+str(png))
    snapshot=zt.Z80Snapshot(str(source));raw=bytes(16384)+snapshot.banks[5]+snapshot.banks[2]+snapshot.banks[0];m=art.initialized(raw);cmap=art.load_colours() if colours is None else colours
    seen=set();comps=[]
    for idx in range(120):
        ptr=m[0x60A3+2*idx]|m[0x60A4+2*idx]<<8
        if ptr in seen:continue
        seen.add(ptr);w=(m[ptr]&15)*8;h=m[ptr+1]
        if not(0<w<=32 and 0<h<=64):continue
        flip=bool(m[ptr]&128);pixels=[];entries={}
        for row in range(h):
            for col in range(w):
                sourcecol=w-1-col if flip else col;a=ptr+2+2*(row*(w//8)+sourcecol//8);mask,inv=m[a:a+2];bit=sourcecol&7
                if not mask&(128>>bit):continue
                code=2 if inv&(128>>bit) else 1;key=f'{a:04X}';entries[key]=[mask|(inv<<8),3]
                pixels.append((col,row,key,bit,code,1 if code==2 else 14))
        part=dict(id=idx,size=w*h,w=w,h=h,dx=0,dy=0,dmir=0,vmir=1,pixels=pixels,entries=entries)
        comps.append(dict(count=1,group=0,parts=[part]))
    identity=colour_identity(lambda a:raw[a]);layout=png.with_name(png.stem+'_layout.json')
    CS.write(CS.choose(comps,{}),str(png),str(layout),art.PALETTE,colours=cmap,unique=False,identity=identity)
    ref=out/(name+'_REFERENCE_ALL_SPRITES.png');CS.write(comps,str(ref),str(ref.with_name(ref.stem+'_layout.json')),art.PALETTE,colours=cmap,unique=False,identity=identity)
    got,_=CS.read(str(png),str(layout));assert got==cmap
    return {'painting':str(png),'layout':str(layout),'reference':str(ref),'figures':len(comps)}

TRAINERS={
 'Infinite lives':[(0xB6C9,0x35,0),(0xA9AC,0x35,0)],
 'Infinite battery':[(0x9E64,0xC8,0xC9),(0xA8D2,0x90,0),(0xAB32,0x90,0)],
 'Protect sectors':[(0xA2ED,0x20,0x18)],
}

def boot_check(nex,source,patch):
    from . import nextboot
    from skoolkit import CSimulator
    from skoolkit.snapshot import Snapshot
    from skoolkit.simutils import from_snapshot
    original=from_snapshot(CSimulator,Snapshot.get(str(source)));expected=bytearray(original.memory[0x4000:])
    for a,old,new in patch.sites:expected[a-0x4000:a-0x4000+len(new)]=new
    bad=[]
    for loader in (False,True):
        got=nextboot.boot(str(nex),original.registers[24],nexload=loader)
        dif=[i for i in CMP if (bool(original.registers[i])!=bool(got['R'][i]) if i==26 else original.registers[i]!=got['R'][i])]
        if dif:bad.append(('registers',loader,dif))
        if bytes(got['mem'][a] for a in range(0x4000,65536))!=expected:bad.append(('48K RAM',loader))
        if got['bad']:bad.append(('boot',loader,got['bad'][:3]))
    return bad

def unit_tests(patch,states,neg=True):
    """Whole prelude ABI at every caller clock and refresh phase; caught controls."""
    from skoolkit.simulator import Simulator
    import copy
    c=Counter()
    for pc,regs,mem in states:
        for speed in range(4):
            for iff in (0,1):
                for refresh in (0,1,126,127,128,129,254,255):
                    rr=list(regs);rr[15]=refresh;rr[26]=iff
                    original=simpool.machine(Simulator,list(mem),rr,'martianoids-unit-original');original.opcodes[mem[pc]]()
                    page=bytearray(patch.ram);page[0x1E30]=speed
                    got,v,model=run_hook(mem,rr,patch,page,speed)
                    if any((bool(original.registers[i])!=bool(got[i]) if i==26 else original.registers[i]!=got[i]) for i in CMP):c['ABI registers differ!']+=1
                    if model.nr[7]!=(3 if pc==0x99EF else speed):c['incoming clock not restored!']+=1
                    if [model.nr[0x50+k] for k in range(8)]!=[255,255,10,11,4,5,0,1]:c['MMU not restored!']+=1
                    expect=bytearray(original.memory[0x4000:])
                    for a,old,new in patch.sites:expect[a-0x4000:a-0x4000+len(new)]=new
                    if expect!=v.mem[0x4000:]:c['ABI game RAM differs!']+=1
                    c['ABI cases']+=1
    if neg and states:
        pc,regs,mem=next(s for s in states if s[0]==0x99EF);broken=copy.deepcopy(patch);start=broken.syms['h_open']-0x2000;at=broken.ram.index(bytes.fromhex('3ef4cd'),start);broken.ram[at+1]+=1
        got,_,_=run_hook(mem,regs,broken);original=simpool.machine(Simulator,list(mem),regs,'martianoids-negative-original');original.opcodes[mem[pc]]()
        c['R negative detected' if got[15]!=original.registers[15] else 'R negative missed!']+=1
    return c

def auto(a,z80,name,out,say):
    from . import rzx as RZ
    out=Path(out);out.mkdir(parents=True,exist_ok=True);ok=True
    say('Game      : '+name)
    say('Engine    : martianoids; original monochrome default, optional ordered Layer 2 colours; original bitmap and logic retained')
    # The archive POK has an unsafe RET and misses a second life-loss path.
    # Feed the generic packager the verified translations, without rewriting
    # the archive or overriding a different, explicitly supplied custom POK.
    trainer_path=out/(name+'_verified.pok')
    trainer_path.write_text(''.join('N'+title+'\n'+''.join(
        ('Z' if i==len(items)-1 else 'M')+f' 8 {addr} {value} {old}\n'
        for i,(addr,old,value) in enumerate(items)) for title,items in TRAINERS.items())+'Y\n')
    requested=getattr(a,'pok',None)
    if not requested or hashlib.sha256(Path(requested).read_bytes()).hexdigest()=='5ebb40196f4df074fd6e07ff350c2667c5a4f78003ab64f8468e3033360b829f':
        a.pok=str(trainer_path)
    say('Trainers  : '+trainer_path.name+'; verified archive translations, all off by default')
    built={}
    for label,enabled,enh,suffix in [('Plain',False,False,''),('Sprites',True,False,'_sprites'),('Enhanced',True,True,'_enhanced')]:
        path=out/(name+suffix+'.nex');p=build(z80,path,enabled,enh);bad=boot_check(path,z80,p);ok &= not bad;built[enh]=p if enabled else built.get(enh)
        say('%-10s: %s %s boot %s'%(label,path.name,hashlib.md5(path.read_bytes()).hexdigest(),'OK' if not bad else str(bad)))
    for recording in list(getattr(a,'rzx',None) or []):
        # A continuous recording is preferred; autosave snapshots are stripped
        # through the shared reader only when explicitly present.
        segments=RZ.read_segments(recording)
        if len(segments)!=1:raise ValueError('Martianoids verification requires a continuous single-segment recording')
        for enh in (False,True):
            p=built[enh];counts,examples,states=verify(p,recording,stop=getattr(a,'quick',None),collect=1)
            bad={k:v for k,v in counts.items() if k.endswith('!')};ok &= not bad
            say('Verify    : %s %s %d frames, %d hooks, full 48K RAM and R; %d colour canvases: %s'%(Path(recording).name,'Enhanced' if enh else 'default',counts['frames'],counts['hooks'],counts['complete colour canvases'],'IDENTICAL' if not bad else str(bad)))
            tests=unit_tests(p,states);failed={k:v for k,v in tests.items() if k.endswith('!')};ok &= not failed
            say('Unit      : '+str(dict(tests)))
            (out/(name+('_enhanced' if enh else '_default')+'_verification.json')).write_text(json.dumps({
                'recording':Path(recording).name,'counts':dict(counts),'examples':examples,'units':dict(tests),
                'runtime_sha256':hashlib.sha256(p.code).hexdigest(),
                'colours_sha256':hashlib.sha256(Path(COLOURS).read_bytes()).hexdigest()},indent=2)+'\n')
            for key,value in examples.items():say('            '+key+': '+str(value[:2]))
    # Separate output folders used by auto/selftest cannot overwrite an owner's
    # active PNG. Existing sheets are intentionally preserved.
    if not (out/(name+'_PAINTING_SPRITES.png')).exists():sheets(z80,out,name)
    say('Result    : '+('PASSED' if ok else 'FAILED'))
    return bool(ok)
