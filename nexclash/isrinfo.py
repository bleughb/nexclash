"""`nexclash.py isr GAME.z80 [--rzx R | --frames N --keys K]` - the game's interrupt handler as
it runs: what a hook must leave intact for it (LEARNINGS 2.1: an interrupt can arrive at any hook
instruction while interrupts are on).

Runs the game (RZX or free run), and from every accepted interrupt until it returns (PC back at
the interrupted address with SP restored) records the instructions executed, then reports:
handler entry chain, registers it READS (IX, IY + offsets, I, alternate set), stack use on the
interrupted stack and any stack switch (LD SP), ports written (7FFD paging), memory it writes
outside its own stack, interrupts that never returned, and which 8K slots it reads / writes / runs
(a RAM page may stay mapped with interrupts on only in a slot the handler never touches).
Game-independent; extend freely (keep
existing report lines; add new ones) and run `python selftest.py --tools`.
"""
import collections
import re
from .simrun import run, disasm

REG_USE = [('IX', re.compile(r'\bIX[HL]?\b|\(IX[+-]')), ('IY', re.compile(r'\bIY[HL]?\b|\(IY[+-]')),
           ('I', re.compile(r'^LD A,I$')), ('R', re.compile(r'^LD A,R$')),
           ("alternate set (EXX)", re.compile(r'^EXX$')), ("AF'", re.compile(r"^EX AF,AF'$"))]
IY_OFF = re.compile(r'\((I[XY])([+-]\d+)\)')


def _flow(reg, text):
    """How an instruction treats index register reg: 'push', 'pop', 'write', 'read' or None."""
    t = text.upper()
    if reg not in t:
        return None
    if t == 'PUSH ' + reg:
        return 'push'
    if t == 'POP ' + reg:
        return 'pop'
    if re.match(r'^LD %s[HL]?,' % reg, t) and '(%s' % reg not in t.split(',', 1)[1]:
        return 'write'
    return 'read'                  # (IX+d), ADD/INC/DEC IX, LD (nn),IX, JP (IX), EX (SP),IX, LD A,IXH...


class IsrTracker:
    def __init__(self):
        self.sim = None
        self.cur = None                # (int_pc, sp_before, start_pc)
        self.ins = {}                  # pc -> text
        self.count = 0
        self.unreturned = 0
        self.entries = collections.Counter()
        self.depth = 0                 # max bytes used below the interrupted SP
        self.switch = collections.Counter()   # pc of instructions that moved SP far away
        self.ports = collections.Counter()
        self.writes = set()
        self.mem = None
        self.dep = {'IX': {}, 'IY': {}}          # reads of the INTERRUPTED code's value: pc -> text
        self.modes = collections.Counter()      # (IM, I) at each accepted interrupt
        self.slots = collections.defaultdict(set)   # 8K slot -> {'r', 'w', 'x'}

    def on_sim(self, sim):
        self.sim = sim

    def on_interrupt(self, sim, prev_pc):
        R = sim.registers
        if self.cur is not None:
            self.unreturned += 1
        self.count += 1
        self.cur = (R[24], R[12])
        self.pending = True
        self.state = {'IX': [True], 'IY': [True]}  # stack of 'holds the entry value' (PUSH/POP)
        self.modes[(R[27] if len(R) > 27 else None, R[14])] += 1

    def before(self, pc):
        if self.cur is None:
            return
        R = self.sim.registers
        if getattr(self, 'pending', False):
            self.pending = False
            self.entries[pc] += 1
        if pc == self.cur[0] and R[12] == self.cur[1]:
            self.cur = None
            return
        self.slots[pc >> 13].add('x')
        if pc not in self.ins:
            m = self.sim.memory
            buf = [0] * 65536
            for k in range(4):
                buf[(pc + k) & 0xFFFF] = m[(pc + k) & 0xFFFF]
            try:
                self.ins[pc] = disasm(buf, pc)[0]
            except Exception:              # noqa: BLE001
                self.ins[pc] = '?'
        text = self.ins[pc]
        for reg in ('IX', 'IY'):
            f = _flow(reg, text)
            if f is None:
                continue
            st = self.state[reg]
            if f == 'push':
                st.append(st[-1])
            elif f == 'pop':
                v = st.pop() if len(st) > 1 else False
                st[-1] = v
            elif f == 'write':
                st[-1] = False
            elif st[-1]:
                self.dep[reg].setdefault(pc, text)

    def after(self, pc, dt):
        if self.cur is None:
            return
        sp, sp0 = self.sim.registers[12], self.cur[1]
        d = (sp0 - sp) & 0xFFFF
        if d < 0x400:
            self.depth = max(self.depth, d)
        elif self.ins.get(pc, '').startswith('LD SP'):
            self.switch[pc] += 1

    def on_write(self, a, v, pc, mem):
        if self.cur is not None:
            self.slots[a >> 13].add('w')
            if a >= 0x4000:
                self.writes.add(a)

    def on_read(self, a, pc, mem):
        if self.cur is not None and not pc <= a <= pc + 3:      # data reads, not instruction bytes
            self.slots[a >> 13].add('r')


def isr(z80, rzx=None, frames=None, keys=None, stop=None):
    from .snapinfo import inspect
    t = IsrTracker()
    n = run(z80, rzx, t, frames=frames, keys=keys, stop=stop)
    lines = ['Source    : %s, %d frames, %d interrupts accepted, %d never returned before the next' % (
        ', '.join(rzx) if rzx else 'free run (keys: %s)' % (keys or 'none'), n, t.count, t.unreturned)]
    if t.modes and None not in [m[0] for m in t.modes]:
        lines.append('Mode      : ' + '; '.join('IM %d, I = 0x%02X%s x%d' % (
            im, i, ' (vector 0x%04X)' % (i * 256 + 0xFF) if im == 2 else '', c) for (im, i), c in t.modes.most_common()))
    else:
        lines += ['Snapshot  : ' + v for k, v in inspect(z80)[0] if k in ('Interrupts', 'IM 2', 'IM 1')]
    if t.entries:
        lines.append('Entered at: ' + ', '.join('%d (0x%04X) x%d' % (a, a, c) for a, c in t.entries.most_common(4)))
    uses = collections.defaultdict(list)
    offs = collections.defaultdict(set)
    for pc, text in sorted(t.ins.items()):
        for name, rx in REG_USE:
            if rx.search(text):
                uses[name].append((pc, text))
        for r, o in IY_OFF.findall(text):
            offs[r].add(int(o))
    lines.append('Executed  : %d distinct instructions in the handler(s)' % len(t.ins))
    need = []
    for reg in ('IX', 'IY'):
        d = sorted(t.dep[reg].items())
        if d:
            lines.append('Reads %s  : the INTERRUPTED code\'s value: %s%s' % (
                reg, '; '.join('%s at %d' % (x, pc) for pc, x in d[:3]), ' (+%d more)' % (len(d) - 3) if len(d) > 3 else ''))
            need.append(reg)
        elif uses[reg]:
            lines.append('Uses %s   : saved / overwritten before any read of the interrupted value' % reg)
    for name, _ in REG_USE:
        if name in ('IX', 'IY'):
            continue
        if uses[name]:
            ex = '; '.join('%s at %d' % (txt, pc) for pc, txt in uses[name][:3])
            more = ' (+%d more)' % (len(uses[name]) - 3) if len(uses[name]) > 3 else ''
            off = (' offsets %s' % sorted(offs[name])) if name in offs else ''
            lines.append('Uses %-5s: %s%s%s' % (name, ex, more, off))
            need.append(name)
    sw = [(pc, t.ins.get(pc, '')) for pc in t.switch]
    lines.append('Stack     : up to %d bytes below the interrupted SP%s' % (
        t.depth, '; switches stack: ' + ', '.join('%s at %d' % (x, pc) for pc, x in sw[:3]) if sw else ''))
    pg = [(pc, x) for pc, x in sorted(t.ins.items()) if x.startswith('OUT')]
    if pg:
        lines.append('Ports     : ' + '; '.join('%s at %d' % (x, pc) for pc, x in pg[:4]) +
                     ' (7FFD writes page memory at C000 / ROM)')
    lines.append('Writes    : %d distinct RAM addresses (incl. its stacks)' % len(t.writes))
    free = [k for k in range(2, 6) if k not in t.slots]
    lines.append('Slots     : %s; never touched: %s%s' % (
        ', '.join('%d (0x%04X) %s' % (k, k << 13, ''.join(c for c in 'rwx' if c in t.slots[k])) for k in sorted(t.slots)),
        ', '.join(str(k) for k in range(8) if k not in t.slots) or 'none',
        ' -> a hook may keep a RAM page mapped in slot %s with interrupts on (LEARNINGS 1.3)' % '/'.join(map(str, free))
        if free else ''))
    keep = ['SP must point at a stack with >= %d free bytes' % (t.depth + 2)] + \
        ['%s unchanged' % x for x in need if x not in ("alternate set (EXX)", "AF'", 'R')]
    if any(x in need for x in ("alternate set (EXX)", "AF'")):
        keep.append('the alternate set is used by the handler (it saves/restores it? check the listing)')
    lines.append('A hook running with interrupts ON must keep: ' + '; '.join(keep))
    return '\n'.join(lines), {'uses': dict(uses), 'reads_entry': {k: dict(v) for k, v in t.dep.items()}, 'depth': t.depth, 'switch': sw, 'count': t.count,
                              'entries': dict(t.entries), 'slots': {k: ''.join(sorted(v)) for k, v in t.slots.items()}}
