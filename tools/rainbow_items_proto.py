# prototype: shadow map of item cells from draw hooks -> predicted screen positions -> check pixels
import sys, collections; sys.path.insert(0,'/home/claude/opt-toolkit')
import skoolkit.rzxplay as rzxplay
from skoolkit.simulator import Simulator
shadow={}; st=collections.Counter(); sample=[]
def scr(y,x): return 0x4000|((y&0xC0)<<5)|((y&7)<<8)|((y&0x38)<<2)|x
class S(Simulator):
    def __init__(self, memory, registers=None, state_=None, config=None):
        super().__init__(memory, registers, state_, config)
        R, mem, ops = self.registers, self.memory, self.opcodes
        def check():
            s=mem[48782]
            for addr,codes in shadow.items():
                row=(addr-0x9F00)>>5; col=addr&31
                y=(row-s)%176
                if y>168: continue
                for code in codes:
                    g=0xF600+16*(code-1)
                    ok=True
                    for r in range(8):
                        m=mem[g+2*r]; gf=mem[g+2*r+1]
                        v=mem[scr(16+y+r,col)]
                        if (v & ~m & 255)!=(gf & ~m & 255): ok=False
                    st['item cell on screen ok' if ok else 'item cell MISMATCH']+=1
                    if len(sample)<6 and ok: sample.append((hex(addr),code,s,y,col))
        def mk(f):
            def g():
                pc=R[24]
                if pc==60853: shadow.pop(R[4]<<8|R[5],None); st['base tile draws']+=1
                elif pc==60965: shadow.setdefault(R[4]<<8|R[5],[]).append(R[0]); st['item draws']+=1
                elif pc==59087: check(); st['renders']+=1
                f()
            return g
        for i in range(256): ops[i]=mk(ops[i])
rzxplay.Simulator, rzxplay.CSimulator = S, None
try: rzxplay.main(['--python','--quiet','--no-screen','--fps','0','--stop',sys.argv[2],sys.argv[1]])
except SystemExit: pass
print(dict(st)); print('items in shadow at end',len(shadow)); print(sample)
