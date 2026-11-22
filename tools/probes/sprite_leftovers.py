#!/usr/bin/env python3
"""Probe: sprites a build leaves visible from the previous program (BRIEFING C2 #26).

    python tools/probes/sprite_leftovers.py BUILD.nex [...] [--steps N]

Invocation: bare .nex builds (nxc.py --bare, or nexclash.py outputs). Each boots in nextboot's simulator
  with all 128 sprite attribute records visible, as another program may leave them, and runs N
  instructions past the stub (default 3,000,000). Every sprite attribute write is replayed (NEXTREG
  $34-$39, $75-$79; ports $303B, $57). Output per build: records still visible that it never wrote
  ("left"), whether it turned sprites on ($15 bit 0), the records it wrote; exit 1 when any build
  turns sprites on with records left.
Limits: no interrupts, so a game waiting for one stops early: "sprites not turned on" means not
  within N (run longer, or a board run with dirty sprites); DMA or copper writes to the sprite
  ports are not seen; pattern contents are not modelled (a left record shows only where its
  pattern has opaque pixels).
Origin: the 2026-11-21 back-catalogue audit (Silkworm Enhanced hid 64 of 128; Bruce Lee, That
  Sinking Feeling, Into the Eagle's Nest, Chase H.Q., Quazatron likewise).
Smoke test: synthetic attribute logs (no game data): 4 hidden by NEXTREG leave 4-127; 512 zero
  bytes on port $57 after $303B = 0 hide all 128; $303B does not move NEXTREG's sprite number.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from nexclash import nextboot, dizzy6, z80n     # noqa: E402

LOG = []
_base = dizzy6._rw_simulator


def _logged():
    Sim = _base()

    class S(Sim):
        def set_tracer(self, tr, *a, **k):
            if tr is None or not hasattr(tr, 'write_port'):
                return Sim.set_tracer(self, tr, *a, **k)
            ed, R, mem = self.after_ED, self.registers, self.memory
            nn, na = ed[0x91], ed[0x92]                    # boot's NEXTREG (paging); the other Z80N ops next
            z80n.install(self, nextreg=lambda r, v: None, strict=False)

            def nn2():
                p = R[24]; LOG.append(('nr', mem[(p + 2) % 65536], mem[(p + 3) % 65536])); nn()

            def na2():
                p = R[24]; LOG.append(('nr', mem[(p + 2) % 65536], R[0])); na()
            ed[0x91], ed[0x92] = nn2, na2
            wp = tr.write_port

            def write_port(regs, port, value, *x):
                LOG.append(('port', port, value)); return wp(regs, port, value, *x)
            tr.write_port = write_port
            return Sim.set_tracer(self, tr, *a, **k)
    return S


def replay(log):
    """-> (visible records, records written) after log, starting from all 128 visible. Port 0x303B and NEXTREG $34
    select separate sprite numbers unless $09 bit 4 locks them together."""
    attr = [[0, 0, 0, 0x80, 0] for _ in range(128)]
    psel = nsel = k = 0
    lock = False
    written = set()
    for kind, a, v in log:
        if kind == 'port':
            if a == 0x303B:
                psel, k = v & 0x7F, 0
                if lock: nsel = psel
            elif a & 0xFF == 0x57:
                written.add(psel)
                attr[psel][k] = v; k += 1
                if (k == 4 and not attr[psel][3] & 0x40) or k == 5:
                    psel, k = (psel + 1) & 0x7F, 0
                    if lock: nsel = psel
        elif a == 0x09:
            lock = bool(v & 0x10)
        elif a == 0x34:
            nsel = v & 0x7F
            if lock: psel, k = nsel, 0
        elif 0x35 <= a <= 0x39:
            written.add(nsel); attr[nsel][a - 0x35] = v
        elif 0x75 <= a <= 0x79:
            written.add(nsel); attr[nsel][a - 0x75] = v; nsel = (nsel + 1) & 0x7F
            if lock: psel = nsel
    return [i for i in range(128) if attr[i][3] & 0x80], written


def ranges(xs):
    out = []
    for x in sorted(xs):
        if out and x == out[-1][1] + 1:
            out[-1][1] = x
        else:
            out.append([x, x])
    return ','.join('%d' % a if a == b else '%d-%d' % (a, b) for a, b in out) or '-'


def check(nex, steps):
    del LOG[:]
    nextboot._rw_simulator = _logged
    try:
        nextboot.boot(nex, -1, limit=steps, sysrom=nextboot.system_rom3()[0], nexload=True)
    except RuntimeError:
        pass                                   # ran its steps
    finally:
        nextboot._rw_simulator = _base
    vis, written = replay(LOG)
    left = [i for i in vis if i not in written]
    on = any(v & 1 for kind, a, v in LOG if kind == 'nr' and a == 0x15)
    return left, on, written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('nex', nargs='+')
    ap.add_argument('--steps', type=int, default=3_000_000)
    a = ap.parse_args(argv)
    bad = 0
    for nex in a.nex:
        left, on, written = check(nex, a.steps)
        verdict = 'LEFT VISIBLE' if left and on else 'ok' if on else 'sprites not turned on'
        bad += bool(left and on)
        print('%s: %s; left %d (%s); written %s' % (os.path.basename(nex), verdict, len(left), ranges(left), ranges(written)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
