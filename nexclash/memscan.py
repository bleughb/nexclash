"""`nexclash.py scan GAME.z80 [--rzx R ...] [--range LO-HI ...]` - which memory a game reads,
writes and executes (PLAYBOOK 3: prove free memory by an access scan, never by zero-check).

Two sources: an RZX (the game as played) or, without --rzx, a free run of the snapshot with a
key schedule (`--keys "5-14:SPACE; 30-:N" --frames 400`) - the start-up path a recording does not
cover (e.g. loader -> game entry -> menu). Run both when the patch uses memory at start-up.

Addresses are CPU addresses; 128K: 0xC000-0xFFFF is counted per RAM bank (bank n at C000).
Report: per range, the untouched spans (never read, written or executed), the first access of
each touched span (PC), spans whose first access is a WRITE (write-first: candidate scratch),
the lowest SP seen. With `--writers`: per range, the instructions (PC) that write it and that read
it as data, with counts - who draws into a screen or back buffer, and who reads it back (logic that
depends on pixels). Game-independent; extend freely (keep existing report lines; add new ones)
and run `python selftest.py --tools`.
"""
import collections
from .simrun import run

READ, WRITE, EXEC = 1, 2, 4


class Scanner:
    def __init__(self, after=None, watch=None):
        self.after_pc = after                               # count only once PC reaches this
        self.active = after is None
        self.flags = bytearray(0xC000 + 8 * 0x4000)       # flat CPU 0..BFFF + 8 banks of C000
        self.first = {}                                     # index -> (kind, pc) of the first access
        self.sp_min = 0x10000
        self.sim = None
        self.watch = watch                                  # [(name, set of indexes)] for --writers
        self.wr = collections.defaultdict(collections.Counter)
        self.rd = collections.defaultdict(collections.Counter)

    def _who(self, i, pc, table):
        for name, idx in self.watch:
            if i in idx:
                table[name][pc] += 1

    def _idx(self, a, mem):
        if a < 0xC000:
            return a
        return 0xC000 + (getattr(mem, 'o7ffd', 0) & 7) * 0x4000 + (a - 0xC000) if hasattr(mem, 'o7ffd') \
            else 0xC000 + (a - 0xC000)

    def on_sim(self, sim):
        self.sim = sim

    def on_read(self, a, pc, mem):
        if not self.active:
            if a == pc == self.after_pc:
                self.active = True
            else:
                return
        i = self._idx(a, mem)
        k = EXEC if a == pc else READ
        if self.watch and k == READ and not pc < a <= pc + 3:
            self._who(i, pc, self.rd)
        if not self.flags[i] & k:
            self.flags[i] |= k
            self.first.setdefault(i, (k, pc))

    def on_write(self, a, v, pc, mem):
        if not self.active:
            return
        i = self._idx(a, mem)
        if self.watch:
            self._who(i, pc, self.wr)
        if not self.flags[i] & WRITE:
            self.flags[i] |= WRITE
            self.first.setdefault(i, (WRITE, pc))

    def after(self, pc, dt):
        if not self.active:
            return
        sp = self.sim.registers[12]
        if sp < self.sp_min:
            self.sp_min = sp


def _label(i, is128):
    if i < 0xC000:
        return '0x%04X' % i
    b, off = divmod(i - 0xC000, 0x4000)
    return ('bank%d:0x%04X' % (b, 0xC000 + off)) if is128 else '0x%04X' % (0xC000 + off)


def _spans(idx, pred):
    out, start = [], None
    for i in idx:
        if pred(i):
            if start is None:
                start = prev = i
            elif i == prev + 1:
                prev = i
            else:
                out.append((start, prev))
                start = prev = i
        elif start is not None:
            out.append((start, prev))
            start = None
    if start is not None:
        out.append((start, prev))
    return out


def parse_range(r, is128):
    """'0x5C00-0x61FF' or 'bank3:0xC000-0xFFFF' -> list of flag indexes."""
    bank = None
    if ':' in r:
        b, r = r.split(':', 1)
        bank = int(b.lower().replace('bank', ''))
    lo, hi = (int(x, 0) for x in r.split('-'))
    if bank is None:
        if hi >= 0xC000 and is128:
            raise ValueError('128K: name the bank for C000-FFFF (bankN:0xC000-0xFFFF)')
        return list(range(lo, hi + 1))
    return [0xC000 + bank * 0x4000 + (a - 0xC000) for a in range(max(lo, 0xC000), hi + 1)]


def scan(z80, rzx=None, frames=None, keys=None, ranges=None, stop=None, after=None, writers=False):
    from skoolkit.snapshot import Snapshot
    is128 = len(Snapshot.get(z80).ram(-1)) == 0x20000
    watch = [(r, set(parse_range(r, is128))) for r in ranges] if writers and ranges else None
    sc = Scanner(after, watch)
    n = run(z80, rzx, sc, frames=frames, keys=keys, stop=stop)
    if not ranges:
        ranges = ['0x4000-0xBFFF'] + (['bank%d:0xC000-0xFFFF' % b for b in range(8)] if is128 else ['0xC000-0xFFFF'])
    lines = ['Source    : %s, %d frames' % (', '.join(rzx) if rzx else 'free run (keys: %s)' % (keys or 'none'), n),
             'Counting  : %s' % ('from the start' if after is None else
                                  'from PC %d (0x%04X)%s' % (after, after, '' if sc.active else ' - NEVER REACHED')),
             'Lowest SP : %d (0x%04X) (any SP value: games that use SP as a data pointer show it here)'
             % (sc.sp_min, sc.sp_min)]
    result = {'frames': n, 'sp_min': sc.sp_min, 'ranges': {}}
    for r in ranges:
        idx = parse_range(r, is128)
        free = [s for s in _spans(idx, lambda i: not sc.flags[i])]
        used = _spans(idx, lambda i: sc.flags[i])
        wfirst = _spans(idx, lambda i: sc.flags[i] and sc.first.get(i, (0,))[0] == WRITE)
        nfree = sum(b - a + 1 for a, b in free)
        lines.append('Range %s: %d of %d bytes untouched' % (r, nfree, len(idx)))
        for a, b in sorted(free, key=lambda x: x[0] - x[1])[:6]:
            lines.append('  untouched   %s-%s (%d bytes)' % (_label(a, is128), _label(b, is128), b - a + 1))
        for a, b in used[:12]:
            k, pc = sc.first.get(a, (0, -1))
            kinds = ''.join(c for f, c in ((READ, 'r'), (WRITE, 'w'), (EXEC, 'x'))
                            if any(sc.flags[i] & f for i in range(a, b + 1)))
            lines.append('  touched     %s-%s (%d bytes, %s), first: %s at PC %d' % (
                _label(a, is128), _label(b, is128), b - a + 1, kinds,
                {READ: 'read', WRITE: 'write', EXEC: 'exec'}.get(k, '?'), pc))
        if len(used) > 12:
            lines.append('  ... %d more touched spans' % (len(used) - 12))
        for a, b in [w for w in wfirst if w[1] - w[0] >= 15][:6]:
            lines.append('  write-first %s-%s (%d bytes)' % (_label(a, is128), _label(b, is128), b - a + 1))
        result['ranges'][r] = {'untouched': [(a, b) for a, b in free], 'touched': used}
        if watch:
            for what, tab in (('writers', sc.wr[r]), ('readers', sc.rd[r])):
                top = tab.most_common(10)
                lines.append('  %-9s %d instructions%s%s' % (what, len(tab), ': ' if top else '', ', '.join(
                    '%d (0x%04X) x%d' % (pc, pc, n) for pc, n in top)))
                rest = rest_spans(tab, {pc for pc, _ in top})
                if rest:
                    # the top 10 are often one unrolled copy loop; the routines that matter (plotters,
                    # text) were hidden below it (Everyone's a Wally, 2026-10-14)
                    lines.append('  %-9s %d more instructions in %d routine span(s): %s%s' % (
                        what + '+', sum(len(s[3]) for s in rest), len(rest), ', '.join(
                            '%d-%d (0x%04X) x%d' % (a, b, a, n) for a, b, n, _ in rest[:20]),
                        ' ...' if len(rest) > 20 else ''))
            result['ranges'][r]['writers'] = dict(sc.wr[r])
            result['ranges'][r]['readers'] = dict(sc.rd[r])
    return '\n'.join(lines), result


def rest_spans(tab, skip, gap=8):
    """The instructions of tab {pc: count} outside skip, joined into spans (next PC within gap bytes:
    one routine) -> [(first pc, last pc, total count, [pcs])], sorted by PC."""
    out = []
    for pc in sorted(p for p in tab if p not in skip):
        if out and pc - out[-1][1] <= gap:
            a, _, n, pcs = out[-1]
            out[-1] = (a, pc, n + tab[pc], pcs + [pc])
        else:
            out.append((pc, pc, tab[pc], [pc]))
    return out


def touched_count(result, r):
    """Touched bytes in a scanned range (for tests)."""
    return sum(b - a + 1 for a, b in result['ranges'][r]['touched'])

