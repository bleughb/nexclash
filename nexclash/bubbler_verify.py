"""Bubbler Enhanced induction and independent original-plotter colour oracle."""
from collections import Counter
from PIL import Image,ImageChops
from skoolkit.simulator import Simulator
from . import hooklib,simpool,rzx,bubbler_art as art
from .dizzy6 import _rw_simulator

MAPS=(94,255,10,11,4,5,0,1)
SCENERY=(0xC5F2,0xC741)
TRANSFORMS=(0xAC40,0xAD9E,0xC857,0xC861,0xC8D9,0xC9C9,0xCA17,0xCA69,0xCB23,0xCB71,0xCBC2)
ORACLE_PCS={0xB43C,*SCENERY,*TRANSFORMS,0xE57F,0xE52B,0xAA9E,0xAAA0,0xA2E0,0xAAB1}

def word(m,a):return m[a]|m[a+1]<<8
def expand(planes):
    im=Image.new('L',(192,128))
    for k in range(8):
        im=ImageChops.add(im,Image.frombytes('1',(192,128),bytes(planes[k])).convert('L').point(lambda v:1<<k if v else 0))
    return im.tobytes()

class Memory:
    def __init__(self,raw,patch,backend=1):
        self.pages=[bytearray(8192)for _ in range(96)]
        self.nr={80+n:p for n,p in enumerate(MAPS)};self.nr[7]=0
        self.pages[24][:]=patch.page;self.pages[95][:]=patch.page
        self.pages[25][:len(patch.aux)]=patch.aux
        self.pages[25][patch.syms['hlib_dma_cap']-0xA000]=backend
        self.pages[24][patch.syms['P_FRONT']&8191]=64
        self.pages[24][patch.syms['P_NEXT']&8191]=70
        for page,data in patch.art['pages'].items():self.pages[page][:]=data
        for page in range(64,76):self.pages[page][:]=bytes([255])*8192
        self.refresh(raw,patch)
        mono=lambda data:b''.join(bytes(255 if v&(128>>b)else 0 for b in range(8))for v in data)
        canvas=bytes(8)+mono(raw[0xE5BB:0xF1BB])+bytes(8192-8)
        for n in range(4):self.pages[28+n][:]=canvas[n*8192:(n+1)*8192]
        self.pages[32][:6144]=mono(raw[0xF500:0xF800])
    def __len__(self):return 65536
    def __getitem__(self,a):
        if isinstance(a,slice):return bytes(self[i]for i in range(*a.indices(65536)))
        page=self.nr[80+(a>>13)]
        return self.pages[95 if page==255 else page][a&8191]
    def __setitem__(self,a,v):
        page=self.nr[80+(a>>13)]
        if page!=255:self.pages[page][a&8191]=v
    def refresh(self,raw,patch):
        for n,page in enumerate(MAPS[2:],2):self.pages[page][:]=raw[n*8192:(n+1)*8192]
        for a,old,new in patch.sites:
            for n,b in enumerate(new):self[a+n]=b
    def game_ram(self):return b''.join(self.pages[p]for p in MAPS[2:])

class Model(hooklib.NextModel):
    def __init__(self,sim,mem,speed):
        maps=dict(mem.nr);super().__init__(sim,speed);self.nr.update(maps);self.nr[7]=speed;mem.nr=self.nr
        self.game_io=[]
    def write_port(self,r,p,v,*args):
        if p not in(0x243B,0x253B) and p&255!=0x6B:self.game_io.append((p,v))
        return super().write_port(r,p,v,*args)

def target(pc,r,raw,patch):
    row=patch.site_rows[pc]
    if 'end' in row:return row['end']
    if row.get('kind')=='call':return row['body']
    if pc==0xAAAB:return word(raw,r[12]) if r[2]==1 else 0xAAAE
    if pc==0xA2E0:return word(raw,r[12])
    if pc==0xAD84:return 0xAD9A
    if pc==0xB4B1:return 0xB4BC if r[3]==0 else 0xB4B5
    return pc+row['size']

def compare(raw,registers,patch,mem,speed=0):
    pc=registers[24];end=target(pc,registers,raw,patch)
    reference=simpool.machine(Simulator,bytearray(raw),list(registers),'bubbler-colour-original',copy=True)
    for step in range(100000):
        if step and reference.registers[24]==end:break
        reference.opcodes[reference.memory[reference.registers[24]]]()
    else:raise AssertionError(('Original displaced routine did not return',hex(pc)))
    mem.nr={80+n:p for n,p in enumerate(MAPS)};mem.nr[7]=speed;mem.refresh(raw,patch)
    sim=simpool.machine(_rw_simulator(),mem,list(registers),'bubbler-colour-hook');model=Model(sim,mem,speed)
    for step in range(2000000):
        if step and sim.registers[24]==end:break
        sim.opcodes[mem[sim.registers[24]]]()
    else:raise AssertionError(('Colour hook did not return',hex(pc),hex(sim.registers[24])))
    differences=[('register',i,reference.registers[i],sim.registers[i])for i in hooklib.CMP_R if reference.registers[i]!=sim.registers[i]]
    expected=bytearray(reference.memory[0x4000:])
    for a,old,new in patch.sites:expected[a-0x4000:a-0x4000+len(new)]=new
    got=mem.game_ram()
    if got!=expected:differences += [('RAM',i+0x4000,a,b)for i,(a,b)in enumerate(zip(expected,got))if a!=b][:20]
    if [mem.nr[80+n]for n in range(8)]!=list(MAPS):differences.append(('mapping',dict(mem.nr)))
    if model.game_io:differences.append(('extra game I/O',model.game_io[:10]))
    return differences,model,end

class Oracle:
    """Eight original CPU bitplanes plus a ninth untouched monochrome plane."""
    def __init__(self,raw,patch):
        from . import bubbler as B
        peek=B._peek(B.prepared(patch.source))
        self.reference=bytes(16384)+bytes(peek(a)for a in range(16384,65536))
        self.colours=patch.colours
        self.planes=[bytearray(raw[0xE5BB:0xF1BB])for _ in range(9)]
        self.saved=[bytearray(raw[0xF500:0xF800])for _ in range(9)]
        self.front=bytearray([255])*49152;self.calls=0;self.committed=False
    def paint(self,m,base,width,height,static):
        row=dict(base=base,width=width,height=height,static=static)
        flip=static and bool((m[base]^self.reference[base])&128)
        result=[{}for _ in range(8)]
        for y in range(height):
            for x in range(width*8):
                sx=width*8-1-x if flip else x
                source=art.byte_address(row,sx,y);dest=art.byte_address(row,x,y)
                bit=128>>(sx&7);ink=self.reference[source]
                cm=self.colours.get(f'{source:04x}')
                value=cm[2][sx&7]if cm else 0
                colour=value-1 if value else(255 if ink&bit else 0)
                for k in range(8):result[k][dest]=result[k].get(dest,0)|((128>>(x&7))if colour&(1<<k)else 0)
        return result
    def at(self,pc,sim):
        m=sim.memory;r=list(sim.registers)
        if pc==0xE57F:
            for plane in self.planes:plane[:]=bytes(3072)
            self.calls=0
        elif pc in(0xAA9E,0xAAA0,0xA2E0):
            address=r[6]*256+r[7]
            if 0xE5BB<=address<0xF1BB:
                for plane in self.planes:plane[address-0xE5BB]=0 if pc==0xA2E0 else r[0]
        elif pc==0xAAB1:
            for plane in self.planes:plane[:3070]=plane[2:3072]
        elif pc in(0xB43C,*SCENERY,*TRANSFORMS):
            if self.calls and self.committed:assert bytes(m[0xE5BB:0xF1BB])==self.planes[8],('Original monochrome oracle before',hex(pc))
            colours=None
            if pc==0xB43C:
                ix=r[8]*256+r[9];a=word(m,26270+2*m[ix]);base=word(m,a+2*(m[ix+1]&31))
                width,height=m[base:base+2];colours=self.paint(m,base,width,height,False)
            elif pc in SCENERY:
                iy=r[10]*256+r[11];base=r[6]*256+r[7]
                colours=self.paint(m,base,m[iy+5]//8,m[iy+6],True)
            ret=word(m,r[12])
            for k in range(9):
                memory=bytearray(m);memory[0xE5BB:0xF1BB]=self.planes[k];memory[0xF500:0xF800]=self.saved[k]
                if k<8 and colours is not None:
                    for address,value in colours[k].items():memory[address]=value
                original=simpool.machine(Simulator,memory,r,slot=f'bubbler-oracle-{k}',copy=True)
                for step in range(20000):
                    if original.registers[24]==ret and original.registers[12]==(r[12]+2)&65535:break
                    original.opcodes[original.memory[original.registers[24]]]()
                else:raise AssertionError(('Original plot did not return',hex(pc)))
                self.planes[k][:]=original.memory[0xE5BB:0xF1BB];self.saved[k][:]=original.memory[0xF500:0xF800]
            if colours is not None:self.calls+=1
        elif pc==0xE52B:
            if self.calls:assert bytes(m[0xE5BB:0xF1BB])==self.planes[8],'Original monochrome oracle commit'
            if self.calls and r[2]==112:self.committed=True
            data=expand(self.planes);offset=(r[12]-0xE5BB)*8
            assert 0<=offset and offset+r[2]*192<=24576
            for y in range(r[2]):self.front[(8+y)*256+48:(8+y)*256+224]=data[offset+y*192:offset+y*192+176]

def verify(patch,path,stop=None,collect=0,progress=None):
    counts=Counter();examples={};states=[];mem=None;oracle=None;serial=None
    blocked=None;span_owner=None;span_end=None
    interiors={a+n:a for a,row in patch.site_rows.items()for n in range(1,row['size'])}
    from . import bubbler as B
    peek=B._peek(B.prepared(patch.source));retclear=set()
    for pc in range(0x5E00,0xE5BB-2):
        if bytes(peek(pc+n)for n in range(3))==bytes.fromhex('CDE0A2'):retclear.add(pc+3)
    def fail(key,detail):
        counts[key+'!']+=1
        if len(examples.setdefault(key,[]))<5:examples[key].append(detail)
    def visit(pc,original):
        nonlocal mem,oracle,serial,blocked,span_owner,span_end
        raw=original.memory;regs=original.registers
        if serial!=id(original):serial=id(original);mem=Memory(raw,patch);oracle=Oracle(raw,patch)
        if span_end==pc:span_owner=span_end=None
        if pc in interiors and span_owner!=interiors[pc]:fail('jump into patched instruction',hex(pc))
        if blocked==pc:blocked=None
        if pc in patch.site_rows and not(blocked is not None and pc in(0xAA9E,0xA2E0)):
            if collect and sum(s[0]==pc for s in states)<collect:
                states.append((pc,list(regs),bytes(raw),[bytes(p)for p in mem.pages]))
            differences,model,end=compare(raw,regs,patch,mem)
            if differences:fail('state differs',(hex(pc),differences[:8]))
            span_owner,span_end=pc,end
            if pc in(0xAA9E,0xA2E0):blocked=end
            counts['hooks']+=1;counts['R comparisons']+=1;counts['RAM bytes compared']+=49152;counts[f'site {pc:04X}']+=1
            if pc==0xE57A:
                front=mem.pages[24][patch.syms['P_FRONT']&8191]
                got=b''.join(mem.pages[front:front+6])
                if got!=oracle.front:fail('published colours differ',sum(a!=b for a,b in zip(got,oracle.front)))
                counts['published pixels compared']+=49152
        if pc in ORACLE_PCS:oracle.at(pc,original)
        if pc==0xE52B:
            want=expand(oracle.planes);got=b''.join(mem.pages[28:32])[8:24584]
            if got!=want:fail('canvas colours differ',sum(a!=b for a,b in zip(got,want)))
            counts['canvases']+=1;counts['canvas pixels compared']+=24576
            if progress and counts['canvases']%50==0:progress(counts)
    pcs=ORACLE_PCS|set(patch.site_rows)|set(interiors)|{a+row['size']for a,row in patch.site_rows.items()}|retclear|{0xAAA4,0xAD9A,0xB4B5,0xB4BC}
    counts['frames'],error=rzx.trace(str(path),pcs,visit,stop)
    if error:fail('recording desynchronised',error)
    return (counts,examples,states)if collect else(counts,examples)

def unit_tests(patch,states):
    """Captured live context, all clocks/IFF/R edges, then broken own code."""
    import copy
    counts=Counter()
    def restored(raw,pages,build,clock):
        memory=Memory(raw,build)
        for page,data in enumerate(pages):memory.pages[page][:]=data
        # The negative's own code/tables win over captured good-build bytes.
        for page in(24,95):memory.pages[page][0x800:0x800+len(build.code)]=build.code
        memory.pages[25][:len(build.aux)]=build.aux
        memory.pages[25][build.syms['hlib_dma_cap']-0xA000]=1
        for name in('V_SPEED','V_SCENERY_SPEED','V_BUILD_SPEED','V_SUB_SPEED','V_COPY_SPEED','V_FAST_SPEED'):
            memory.pages[24][build.syms[name]&8191]=clock
        return memory
    def run(state,build,clock=0,iff=0,refresh=None):
        pc,regs,raw,pages=state;regs=list(regs);regs[25]=1000;regs[26]=iff
        if refresh is not None:regs[15]=refresh
        memory=restored(raw,pages,build,clock)
        diff,model,_=compare(raw,regs,build,memory,clock)
        return diff,model,memory
    for state in states:
        for clock in range(4):
            for iff in(0,1):
                for refresh in(0,127,128,255):
                    diff,model,memory=run(state,patch,clock,iff,refresh)
                    if diff:counts['ABI state differs!']+=1
                    counts['ABI cases']+=1
    mutations=[]
    bad=copy.deepcopy(patch);code=bytearray(bad.code)
    start=bad.syms['h_actor_source']-0x2800;at=code.index(bytes.fromhex('3EF3CD'),start)
    code[at+1]+=1;bad.code=bytes(code);mutations.append(('refresh offset',bad,{0xB43F}))
    bad=copy.deepcopy(patch);code=bytearray(bad.code);at=code.index(bytes.fromhex('ED9151FF'),start)
    code[at+3]=24;bad.code=bytes(code);mutations.append(('MMU restoration',bad,{0xB43F}))
    bad=copy.deepcopy(patch);code=bytearray(bad.code);at=code.index(bytes.fromhex('ED910703'),bad.syms['h_open']-0x2800)
    code[at+3]=0;bad.code=bytes(code);mutations.append(('clock switch',bad,{0xCE10}))
    for name,siteset in [('colour_draw',{0xB4B1,0xC60C,0xC78E}),('colour_restore',{0xAD9E}),('colour_prepare',{0xCE19,0xE52B})]:
        bad=copy.deepcopy(patch);aux=bytearray(bad.aux);aux[bad.syms[name]-0xA000]=0xC9;bad.aux=bytes(aux)
        mutations.append((name+' disabled',bad,siteset))
    for name,bad,siteset in mutations:
        detected=False
        for state in states:
            if state[0]not in siteset:continue
            good,goodmodel,goodmem=run(state,patch);assert not good,good
            try:
                diff,model,memory=run(state,bad)
                detected=bool(diff or model.nr[7]!=goodmodel.nr[7]or
                              any(memory.pages[p]!=goodmem.pages[p]for p in range(28,76)))
            except (AssertionError,IndexError):detected=True
            if detected:break
        counts[('negative caught: 'if detected else'negative missed! ')+name]+=1
        if not detected:counts['negative missed!']+=1
    return counts
