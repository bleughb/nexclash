"""`nexclash.py inspect GAME.z80` - what kind of snapshot this is, before any other work
(PLAYBOOK 0b): machine, paging/ROM, where PC is (game or ROM/BASIC), BASIC program and its USR
targets, interrupt mode and handler, stack. Warnings for states that need extra work.

Game-independent; extend freely (keep existing line labels, add new ones) and run
`python selftest.py --tools`.
"""
from .simrun import addr_view, disasm

ROM_PLACES = [(0x0038, 0x0052, 'IM 1 handler'), (0x03B5, 0x03F8, 'BEEPER (game sound)'),
              (0x04C2, 0x053F, 'SA-BYTES (tape save)'), (0x0556, 0x0605, 'LD-BYTES (tape load)'),
              (0x0D6B, 0x0D94, 'CLS'), (0x10A8, 0x111D, 'KEY-INPUT'), (0x12A2, 0x12CF, 'MAIN-EXEC (BASIC)'),
              (0x15D4, 0x15E6, 'WAIT-KEY'), (0x1B76, 0x1B8A, 'STMT-RET (BASIC)'),
              (0x1F3A, 0x1F54, 'PAUSE (key wait)')]


def _rom_place(pc):
    for a, b, name in ROM_PLACES:
        if a <= pc < b:
            return name
    return '0x%04X' % pc


def _w(m, a):
    return m[a] | m[(a + 1) & 0xFFFF] << 8


def _usr_targets(m):
    """Numbers after the USR token (0xC0) in the BASIC program (PROG..VARS)."""
    prog, vars_ = _w(m, 23635), _w(m, 23627)
    out = []
    if not 23755 <= prog < vars_ <= 0xFFFF:
        return out
    i = prog
    while i < vars_ - 1:
        if m[i] == 0xC0:
            j = i + 1
            while j < vars_ and m[j] != 14 and m[j] not in (13, 58):
                j += 1
            if j + 5 < vars_ and m[j] == 14 and m[j + 1] == 0 and m[j + 2] in (0, 0xFF):
                out.append(m[j + 3] | m[j + 4] << 8)
            i = j
        i += 1
    return out


def _follow(m, a, n=4):
    """Follow JP nn chains from a; returns the list of addresses."""
    chain = [a]
    while n and m[a] == 0xC3:
        a = _w(m, a + 1)
        chain.append(a)
        n -= 1
    return chain


def inspect(path):
    """-> (facts [(label, text)], warnings [text])."""
    from skoolkit.snapshot import Snapshot
    s = Snapshot.get(path)
    m = addr_view(s)
    is128 = len(s.ram(-1)) == 0x20000
    facts, warn = [], []
    facts.append(('Machine', '128K' if is128 else '48K'))
    if is128:
        p = s.out7ffd
        facts.append(('7FFD', '0x%02X: ROM %d (%s), bank %d at C000, screen %s%s' % (
            p, (p >> 4) & 1, '48K BASIC' if p & 16 else '128K editor', p & 7, 'shadow (7)' if p & 8 else 'normal (5)',
            ', paging LOCKED' if p & 32 else '')))
        if not p & 16:
            warn.append('ROM 0 (128K editor) selected: the Next has no ROM 0 image for the patched build '
                        '(alt ROM image 0 is not filled) - run to a point where the game selects ROM 1')
    pc = s.pc
    if pc < 0x4000:
        where = 'ROM %s' % _rom_place(pc)
    elif pc < 0x5B00:
        where = 'screen memory (!)'
    elif pc < 0x5CC0:
        where = 'printer buffer / system variables'
    else:
        where = 'RAM'
    facts.append(('PC', '%d (0x%04X) - %s' % (pc, pc, where)))
    prog, vars_ = _w(m, 23635), _w(m, 23627)
    basic = 23755 <= prog < vars_ and m[prog] < 64
    usr = _usr_targets(m) if basic else []
    if basic:
        from skoolkit.basic import BasicLister
        try:
            lines = BasicLister().list_basic(m).split('\n')
        except Exception:                        # noqa: BLE001 - listing is best effort
            lines = []
        facts.append(('BASIC', 'program %d-%d, %d line(s); USR targets: %s' % (
            prog, vars_ - 1, len(lines), ', '.join('%d (0x%04X)' % (u, u) for u in usr) or 'none')))
        for ln in lines[:8]:
            facts.append(('', '  ' + ln[:110]))
    if pc < 0x4000 and basic and s.im == 1:
        warn.append('loader snapshot: a BASIC program is running (PC in ROM). The game starts at a USR '
                    'target; run the loader to it in the toolkit (keys with `scan --keys`), build from there')
        if is128:
            warn.append('128K BASIC: every statement pages ROM 0 - the Next build must not run it '
                        '(Commando: loader run in the toolkit + a front end, games/commando.md)')
    facts.append(('RAMTOP', '%d (0x%04X)' % (_w(m, 23730), _w(m, 23730))))
    facts.append(('Interrupts', 'IM %d, %s, I = 0x%02X' % (s.im, 'EI' if s.iff1 else 'DI', s.i)))
    if s.im == 2:
        va = s.i * 256 + 0xFF
        h = _w(m, va)
        uniform = all(m[(s.i * 256 + k) & 0xFFFF] == m[s.i * 256] for k in range(257))
        chain = _follow(m, h)
        facts.append(('IM 2', 'vector at 0x%04X -> %s%s' % (va, ' -> '.join('%d (0x%04X)' % (a, a) for a in chain),
                                                         ' (table of 257 equal bytes)' if uniform else
                                                         ' (table NOT uniform: the bus byte matters)')))
        if chain[-1] < 0x4000:
            warn.append('IM 2 handler in ROM (0x%04X)' % chain[-1])
        else:
            try:
                ins = []
                a = chain[-1]
                for _ in range(6):
                    t, n = disasm(m, a)
                    ins.append(t)
                    a += n
                facts.append(('', '  handler: ' + ' / '.join(ins)))
            except Exception:                    # noqa: BLE001
                pass
    elif s.im == 1:
        facts.append(('IM 1', 'ROM 0x0038 (hooks that page slot 0 must DI)'))
    sp = s.sp
    top = ' '.join('%04X' % _w(m, (sp + 2 * k) & 0xFFFF) for k in range(4))
    facts.append(('Stack', 'SP %d (0x%04X); top words %s' % (sp, sp, top)))
    if 0x5B00 <= sp <= 0x5C00:
        warn.append('stack in the printer buffer (0x5B00 strategy unavailable)')
    facts.append(('Border', str(s.border)))
    return facts, warn


def report(path):
    facts, warn = inspect(path)
    out = ['%-10s: %s' % (k, v) if k else '%-10s  %s' % ('', v) for k, v in facts]
    out += ['WARNING   : ' + w for w in warn] or ['WARNING   : none']
    return '\n'.join(out)
