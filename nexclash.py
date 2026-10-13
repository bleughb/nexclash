#!/usr/bin/env python3
"""nexclash - ZX Spectrum .z80 -> Spectrum Next .nex, with the player drawn as hardware sprites.
Copyright (C) 2026 the nexclash contributors. GPL-3.0-or-later (see LICENSE).

  python nexclash.py patch GAME.z80                     YOUR game: plain + sprite .nex, says if verified
  python nexclash.py new GAME.z80                       not supported yet: session folder to add it
  python nexclash.py contribute NAME [--report R]       zip what a session added, for upload
  python nexclash.py auto GAME.z80 [--rzx MY.rzx ...]   everything: plain + patched .nex + report
      --strategy altrom|printer|slot1   patch memory (default: altrom where proven; old builds: printer/slot1)
      --allow-60hz                      keep the Next's video rate (default: 50 Hz forced, as verified)
  python nexclash.py identify GAME.z80                  which engine (and the derived profile)
  python nexclash.py record GAME.z80 [-o OUT.rzx]       automatic (or scripted) RZX recording
  python nexclash.py convert GAME.z80 [--rzx R]         plain .nex only (tail placement checked)
  python nexclash.py verify GAME.z80 --rzx R            differential test of the patched build
  python nexclash.py rzx info FILE | rzx merge A B -o C | rzx strip A -o B
Analysis (any game; PLAYBOOK 0b / 3 / 3b):
  python nexclash.py inspect GAME.z80                   snapshot kind: loader?, 48K/128K, ROM, IM, stack
  python nexclash.py scan GAME.z80 [--rzx R] [--range LO-HI] [--after PC]   memory read/written/run
  python nexclash.py isr GAME.z80 [--rzx R]             interrupt handler: what hooks must keep intact
  python nexclash.py cost GAME.z80 --rzx R --at ADDR [--group IX]   a routine's cost per call / frame
  python nexclash.py preview GAME.z80 --rzx R [--at F,F] [--plot ADDR] [--buffer A:S:L] -o x.png   contact sheet
  (no --rzx: free run of the snapshot, --frames N --keys "5-14:SPACE; 30-:N"; --stop N frames)

Recording options (record and auto):
  --start "SPACE"            keys that start the game, e.g. "4 5, wait 20, 0 5"
  --script FILE              fully scripted input (see nexclash/recorder.py for the format)
  --keys Z,X,SPACE           inputs to explore with (skip input learning); K:LEFT etc. = Kempston
  --input auto|keyboard|kempston
  --frames N (kept, default 6000)  --budget N (explored, default 20000)  --seed N
Your own recordings: --rzx FILE (repeatable) are analysed and verified too; --no-record skips
the automatic one.
"""
import argparse, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'nexclash'))
try:
    import skoolkit  # noqa
except ImportError:
    for p in (r'C:\skoolkit-10.1', os.path.expanduser('~/skoolkit')):
        if os.path.isdir(p):
            sys.path.insert(0, p)
    import skoolkit  # noqa

from skoolkit.snapshot import Snapshot
from nexclash.identify import identify
from nexclash import recorder, rzx as rzxmod, build as B, z80tonex as zt
from nexclash.machine import parse_inputs, FAST


def rec_args(ap):
    ap.add_argument('--start'); ap.add_argument('--script'); ap.add_argument('--keys')
    ap.add_argument('--input', default='auto', choices=['auto', 'keyboard', 'kempston'])
    ap.add_argument('--frames', type=int, default=6000); ap.add_argument('--budget', type=int, default=20000)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--room-threshold', type=float, default=0.25,
                    help='fraction of attribute cells that must differ for a new room (default 0.25)')


def do_record(a, z80, out):
    keys = [k for s in a.keys.split(',') for k in parse_inputs(s)] if a.keys else None
    script = open(a.script).read() if a.script else None
    budget = a.budget if FAST else min(a.budget, 8000)
    return recorder.record(z80, out, a.start, script, a.input, a.frames, budget, a.seed, keys,
                           room_threshold=getattr(a, 'room_threshold', 0.25))


class _SnapInfo:
    def __init__(self, s):
        self.banks = {5: bytes(s.memory[16384:32768])}
        self.sp = s.sp



def _auto_dizzy6(a, s, z80, name, out, rzxs, prof, say, rep, dec=None):
    """TID engine + mirrored player copy (Dizzy 6): one analysis + one first-access pass per RZX,
    tail in the player's undo buffer (proven write-first), plain + sprite build, verify, mirror selftest."""
    from nexclash.analyse import analyse
    from nexclash.verify import verify
    from nexclash import dizzy6 as D6
    if not rzxs and dec is None:
        say('Sprites   : not built - needs a recording'); return _finish(out, name, rep)
    mem = list(s.memory[0:65536])
    tprof = dict(prof, engine='tid')
    U, USZ = tprof['undo_buffer'], 88
    proven, analyses = True, []
    for r in ([] if dec is not None else rzxs):
        t = time.time()
        an = analyse(tprof, r, s.sp, stop=a.quick)
        fa = D6.first_access(r, U, U + USZ)
        analyses.append((r, an))
        ev = an['events']
        say('Analysis  : %s (%.0fs) plots %d, boxes %d, pixel tests %d, player-dependent %d; undo buffer first access %s' % (
            os.path.basename(r), time.time() - t, ev.get('plot (not drawn)', 0) + ev.get('plot (drawn)', 0),
            ev.get('box (drawn)', 0) + ev.get('box (not drawn)', 0), ev.get('pixel tests', 0),
            ev.get('PIXEL TESTS THAT DEPEND ON THE PLAYER', 0), 'write' if set(fa) == {'w'} else 'NOT write-first: ' + fa))
        proven &= set(fa) == {'w'}
    if dec is not None:
        an, proven = _an_from_decisions(dec), dec['tail_proven']
        vread, smod = dec['virtual_read_needed'], dec['self_modified_sites']
    else:
        an = _combine([x for _, x in analyses])
        vread = any(x['virtual_read_needed'] for _, x in analyses)
        smod = any(bool(x['self_modified_sites']) for _, x in analyses)
        _write_decisions(out, name, an, {'tail_proven': proven, 'virtual_read_needed': vread,
                                         'self_modified_sites': smod})
    tail = U if proven else None
    plain = os.path.join(out, name + '.nex')
    zt.convert(z80, plain, tail, True, quiet=True)
    say('Plain     : %s  %s' % (os.path.basename(plain), ('tail in the player undo buffer at %d (write-first in every RZX)' % U)
                                if proven else 'WARNING: tail unproven; converter default used'))
    sprites = os.path.join(out, name + '_sprites.nex')
    why = []
    if not proven:
        why.append('undo buffer not proven write-first')
    if an['rom_used']:
        why.append('game reads the ROM (slot-1 page would hide it)')
    if vread:
        why.append("game logic reads the player's pixels")
    if smod:
        why.append('the game writes to a patch site')
    if a.strategy not in (None, 'slot1'):
        why.append('--strategy %s: Dizzy 6 keeps its self-modifying plotter copy in the slot-1 RAM page (slot1 only)'
                   % a.strategy)
    if why:
        say('Sprites   : not built - ' + '; '.join(why)); return _finish(out, name, rep)
    patch = D6.Dizzy6Patch(tprof, mem, U, USZ)
    conv = zt.convert(z80, sprites, None, True, quiet=True, patch=patch)
    _boot(say, z80, sprites, patch, conv)
    say('Sprites   : %s  (slot1 + mirror copy at 0x%04X; %d patterns%s)' % (
        os.path.basename(sprites), D6.COPY_ORG, patch.num_patterns, '; rebuilt, not re-verified' if dec else ''))
    if dec is not None:
        return _finish(out, name, rep)
    ok = True
    for r, _ in analyses:
        t = time.time()
        v = verify(tprof, patch, r, stop=a.quick)
        ok &= v['passed']
        say('Verify    : %s %s (%.0fs)' % (os.path.basename(r), 'PASSED' if v['passed'] else 'FAILED', time.time() - t))
        say('            ' + ', '.join('%s %d' % kv for kv in sorted(v['stats'].items())))
        for e in v['examples']:
            say('            example: %s' % (e,))
    p2 = D6.Dizzy6Patch(tprof, mem, U, USZ)
    zs = zt.Z80Snapshot(z80)
    p2.apply(zs)
    pm = [0] * 0x2000 + list(p2.page) + list(zs.banks[5] + zs.banks[2] + zs.banks[0])
    n, bad = D6.mirror_selftest(tprof, p2, mem, pm)
    ok &= not bad
    say('Mirror    : copy vs original plotter/eraser, %d cases, %s' % (n, 'IDENTICAL' if not bad else 'MISMATCH %s' % bad[:3]))
    if not ok:
        say('RESULT    : sprite build FAILED verification - do not use; send this folder to the agent')
    _finish(out, name, rep)

def cmd_auto(a):
    from nexclash.analyse import analyse
    from nexclash.verify import verify
    z80 = a.z80
    name = os.path.splitext(os.path.basename(z80))[0]
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(z80)), name + '_nexclash')
    os.makedirs(out, exist_ok=True)
    rep = []
    say = lambda s='': (rep.append(s), print(s))
    s = Snapshot.get(z80)
    from nexclash import rainbow as _rb                       # Rainbow Islands (128K) engine
    if _rb.is_rainbow(s):
        ok = _rb.auto(a, z80, name, out, say)
        _finish(out, name, rep)
        return ok
    from nexclash import wally as _wa                         # Everyone's a Wally (128K snapshot)
    if _wa.is_wally(s):
        ok = _wa.auto(a, z80, name, out, say)
        _finish(out, name, rep)
        return ok
    from nexclash import chuckie as _ce                       # Chuckie Egg (48K)
    if _ce.is_chuckie(s):
        ok = _ce.auto(a, z80, name, out, say)
        _finish(out, name, rep)
        return ok
    from nexclash import commando as _co                      # Commando (128K)
    if _co.is_commando(s):
        ok = _co.auto(a, z80, name, out, say)
        _finish(out, name, rep)
        return ok
    from nexclash import midres as _mr                        # Midnight Resistance (128K)
    if _mr.is_midres(s):
        ok = _mr.auto(a, z80, name, out, say)
        _finish(out, name, rep)
        return ok
    from nexclash import smashtv as _st                       # Smash TV (48K, BASIC loader)
    if _st.is_smashtv(s):
        ok = _st.auto(a, z80, name, out, say)
        _finish(out, name, rep)
        return ok
    if s.machine != '48K' and len(s.ram()) > 49152:
        say('128K snapshot: sprite patching supports 48K games only; plain conversion only.')
    prof = identify(s.memory[0:65536])
    eng = prof['engine']
    say('Game      : %s' % name)
    say('Engine    : %s%s' % (eng, (' (%s)' % prof['game']) if 'game' in prof else ''))
    for n in prof.get('notes', []):
        say('            note: ' + n)
    if prof.get('hint'):
        say('            ' + prof['hint'])
    json.dump({k: v for k, v in prof.items()}, open(os.path.join(out, name + '_profile.json'), 'w'), indent=1)
    rzxs = list(a.rzx or [])
    dec = json.load(open(a.decisions)) if getattr(a, 'decisions', None) else None
    if dec is not None:
        a.no_record = True
        say('Rebuild   : from stored build decisions %s - no analysis, no verification (the evidence '
            'record holds those)' % os.path.basename(a.decisions))
    if not a.no_record:
        t = time.time()
        auto = os.path.join(out, name + '_auto.rzx')
        r = do_record(a, z80, auto)
        say('Recording : %s  (%.0fs; start=%s; inputs=%s; %s rooms; %d frames)' % (
            os.path.basename(auto), time.time() - t, r['start'], r['inputs'], r.get('rooms', '?'), r['frames']))
        if r['inputs'].startswith('none') or r['start'] == 'none detected':
            say('            weak recording: try --start/--keys, or send your own RZX (--rzx)')
        rzxs.insert(0, auto)
    if not rzxs and dec is None:
        say('No recording: plain conversion uses the converter default tail (unchecked).')
    if eng in ('dizzy5', 'dizzy5_like'):
        return _auto_dizzy5(a, s, z80, name, out, rzxs, say, rep, dec)
    if eng == 'tid_mirror' and prof.get('ok'):
        return _auto_dizzy6(a, s, z80, name, out, rzxs, prof, say, rep, dec)
    tid = eng == 'tid' and prof.get('ok')
    analyses = []
    for r in ([] if dec is not None else rzxs):
        t = time.time()
        an = analyse(prof if tid else None, r, s.sp, stop=a.quick)
        analyses.append((r, an))
        ev = an['events']
        say('Analysis  : %s (%.0fs) %s' % (os.path.basename(r), time.time() - t,
            ('plots %s, boxes %s, pixel tests %s, player-dependent %s' % (
                ev.get('plot (not drawn)', 0) + ev.get('plot (drawn)', 0), ev.get('box (drawn)', 0) + ev.get('box (not drawn)', 0),
                ev.get('pixel tests', 0), ev.get('PIXEL TESTS THAT DEPEND ON THE PLAYER', 0))) if tid else 'access scan'))
    an = _combine([x for _, x in analyses]) if analyses else None
    fp = _fingerprint(s.memory, prof) if tid and dec is None else None
    if fp:
        for r, x in analyses:
            if not r.endswith('_auto.rzx'):
                _learn(fp, name, x['stack_low_water'], os.path.basename(r))
        ev = _evidence(fp)
        if an is not None and ev.get('stack_low_water', 65536) < an['stack_low_water']:
            an['stack_low_water'] = ev['stack_low_water']
            say('Evidence  : stack used down to 0x%04X (proven by %s)' % (ev['stack_low_water'], ev.get('source')))
    if dec is not None:
        an = _an_from_decisions(dec)
    elif an is not None:
        _write_decisions(out, name, an)
    plain = os.path.join(out, name + '.nex')
    why = B.plain(z80, plain, an)
    say('Plain     : %s  %s' % (os.path.basename(plain), why))
    sprites = os.path.join(out, name + '_sprites.nex')
    if eng == 'dizzy1_xor':                                    # Dizzy 1: every figure on Layer 2
        from nexclash import dizzy1 as _d1
        if a.strategy not in (None, 'altrom'):
            say('            note: the Dizzy 1 engine is altrom-only; --strategy %s ignored' % a.strategy)
        _d1.auto(a, z80, sprites, say, rzxs if dec is None else [], _boot)
    elif eng == 'tid_legacy':
        if a.strategy not in (None, 'printer'):
            say('            note: dedicated builder is printer-only; --strategy %s ignored' % a.strategy)
        mod = __import__('dizzy_patch')
        p = mod.DizzyPatch()
        conv = zt.convert(z80, sprites, None, True, quiet=True, patch=p)
        _boot(say, z80, sprites, p, conv)
        say('Sprites   : %s  (dedicated builder; verified during development)' % os.path.basename(sprites))
    elif tid:
        if an is None:
            say('Sprites   : not built - needs a recording to prove the patch is safe'); return _finish(out, name, rep)
        strat, reason, tail = B.choose_tid_strategy(_SnapInfo(s), an, a.strategy)
        if strat is None:
            say('Sprites   : not built - ' + reason)
            if not an['rom_used'] and s.sp - an['stack_low_water'] < 54:
                say('            the recordings prove only %d bytes of dead stack below SP 0x%04X (54 needed).'
                    % (s.sp - an['stack_low_water'], s.sp))
                say('            Record a longer RZX (open the inventory, talk, lose a life) and rerun with --rzx.')
            return _finish(out, name, rep)
        if dec is not None:
            patch = B.TidPatch(prof, strat, tail)
            conv = zt.convert(z80, sprites, None, True, quiet=True, patch=patch)
            _boot(say, z80, sprites, patch, conv)
            say('Sprites   : %s  (%s: %s; %d patterns; rebuilt, not re-verified)' % (
                os.path.basename(sprites), strat, reason, patch.num_patterns))
            return _finish(out, name, rep)
        if any(x['virtual_read_needed'] for _, x in analyses):
            say('Sprites   : not built - game logic reads the player\'s pixels (needs a virtual read;')
            say('            see PLAYBOOK step 4). Send this report + RZX to the agent.'); return _finish(out, name, rep)
        if any(x['self_modified_sites'] for _, x in analyses):
            say('Sprites   : not built - the game writes to a patch site (self-modifying code)'); return _finish(out, name, rep)
        patch = B.TidPatch(prof, strat, tail)
        conv = zt.convert(z80, sprites, None, True, quiet=True, patch=patch)
        _boot(say, z80, sprites, patch, conv)
        say('Sprites   : %s  (%s: %s; %d patterns%s)' % (os.path.basename(sprites), strat, reason, patch.num_patterns,
                                                       '' if prof.get('box') else '; no box hook'))
        ok = True
        for r, _ in analyses:
            t = time.time()
            v = verify(prof, patch, r, stop=a.quick)
            ok &= v['passed']
            say('Verify    : %s %s (%.0fs)' % (os.path.basename(r), 'PASSED' if v['passed'] else 'FAILED', time.time() - t))
            say('            ' + ', '.join('%s %d' % kv for kv in sorted(v['stats'].items())))
            for e in v['examples']:
                say('            example: %s' % (e,))
        if not ok:
            say('RESULT    : sprite build FAILED verification - do not use; send this folder to the agent')
    else:
        say('Sprites   : not built - unknown engine. Add it with Claude: python nexclash.py new %s' % os.path.basename(z80))
    _finish(out, name, rep)


def _auto_dizzy5(a, s, z80, name, out, rzxs, say, rep, dec=None):
    """Dizzy V engine: optional loader pre-run, one analysis pass per RZX, plain + sprite build,
    differential verify."""
    from nexclash import dizzy5 as D5
    from nexclash.loader import prerun
    if not rzxs:
        say('Plain     : %s  %s' % (name + '.nex', B.plain(z80, os.path.join(out, name + '.nex'),
                                                     _an_from_decisions(dec) if dec else None)))
        say('Sprites   : not built - needs a recording (%s)' % (
            'the loader start state is replayed from it' if dec else 'to prove the patch is safe'))
        return _finish(out, name, rep)
    src = z80
    prof = D5.identify5(s.memory[0:65536])
    if not (prof and prof.get('engine') == 'dizzy5'):
        pre = os.path.join(out, name + '_start.z80')
        ok = lambda mem: (D5.identify5(mem) or {}).get('engine') == 'dizzy5'
        path, frame, pc = prerun(rzxs[0], ok, pre)
        if path is None:
            say('Start     : engine never appears in %s - send this folder to the agent' % os.path.basename(rzxs[0]))
            return _finish(out, name, rep)
        src = path
        prof = D5.identify5(Snapshot.get(path).memory[0:65536])
        say('Start     : loader snapshot; game relocated by frame %d of %s -> start state PC=%d (%s)'
            % (frame, os.path.basename(rzxs[0]), pc, os.path.basename(path)))
    json.dump({k: v for k, v in prof.items()}, open(os.path.join(out, name + '_profile.json'), 'w'), indent=1)
    if not prof.get('ok'):
        say('Sprites   : not built - profile incomplete: ' + '; '.join(prof.get('notes', [])))
        return _finish(out, name, rep)
    smem = Snapshot.get(src).memory[0:65536]
    if dec is not None:                        # rebuild: start state from the recording, facts stored
        plain = os.path.join(out, name + '.nex')
        say('Plain     : %s  %s' % (os.path.basename(plain), B.plain(z80, plain, _an_from_decisions(dec))))
        patch = D5.D5Patch(prof, prof['undo_buffer'], prof['undo_size'], strategy=a.strategy or 'altrom')
        sprites = os.path.join(out, name + '_sprites.nex')
        conv = zt.convert(src, sprites, None, True, quiet=True, patch=patch)
        _boot(say, src, sprites, patch, conv)
        say('Sprites   : %s  (%s; rebuilt, not re-verified)' % (os.path.basename(sprites), patch.strategy))
        return _finish(out, name, rep)
    ans = []
    for r in rzxs:
        t = time.time()
        x = D5.analyse5(prof, r, s.sp, stop=a.quick)
        ans.append((r, x))
        ev = x['events']
        say('Analysis  : %s (%.0fs) plots %d, erases %d, frames %s, overwrites while drawn %d (visual only)' % (
            os.path.basename(r), time.time() - t, ev.get('plot (not drawn)', 0) + ev.get('plot (DRAWN)', 0),
            ev.get('erase (drawn)', 0) + ev.get('erase (NOT DRAWN)', 0), len(x['frames']),
            sum(n for (pc, cls, when), n in x['diff_writes'] if when == 'drawn' and cls != 'xor')))
    an = _combine([x for _, x in ans])
    an['fa'] = bytes(min(v for v in col if v) if any(col) else 0 for col in zip(*[x['fa'] for _, x in ans])) \
        if len(ans) > 1 else ans[0][1]['fa']
    _write_decisions(out, name, an)
    plain = os.path.join(out, name + '.nex')
    say('Plain     : %s  %s' % (os.path.basename(plain), B.plain(z80, plain, an)))
    why = [w for _, x in ans for w in D5.refusals(prof, x, smem)]
    # hook page = ROM copy; the game must never read the ROM bytes the hooks replace
    patch = D5.D5Patch(prof, prof['undo_buffer'], prof['undo_size'], strategy=a.strategy or 'altrom')
    lo, hi = D5.ORG, D5.ORG + len(patch.code) + 8 * prof['num_frames'] + 20
    if any(x['rd_game'][q] for _, x in ans for q in range(lo, hi)):
        why.append('the game reads ROM 0x%04X-0x%04X (hook page area)' % (lo, hi))
    # start-up tail goes in the undo buffer: written by every plot before the eraser reads it
    U = prof['undo_buffer']
    if any(x['fa_game'][q] == 1 for _, x in ans for q in range(U, U + prof['undo_size'])):
        why.append('undo buffer is read before it is written (tail location not proven)')
    if why:
        say('Sprites   : not built - ' + why[0])
        for w_ in why[1:4]:
            say('            ' + w_)
        return _finish(out, name, rep)
    sprites = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(src, sprites, None, True, quiet=True, patch=patch)
    _boot(say, src, sprites, patch, conv)
    # every ROM byte the game reads in 0x2000-0x3FFF must read the same from the slot-1 page
    from skoolkit import ROM48, read_bin_file
    rom = read_bin_file(ROM48, 16384)
    wrong = [q for q in range(0x2000, 0x4000) if any(x['rd_game'][q] for _, x in ans)
             and patch.page[q - 0x2000] != rom[q]]
    if wrong:
        os.remove(sprites)
        say('Sprites   : not built - slot-1 page differs from ROM at %d byte(s) the game reads (first 0x%04X)'
            % (len(wrong), wrong[0]))
        return _finish(out, name, rep)
    say('ROM page  : matches the ROM at all %d ROM bytes the recordings read in 0x2000-0x3FFF' % sum(
        1 for q in range(0x2000, 0x4000) if any(x['rd_game'][q] for _, x in ans)))
    say('Sprites   : %s  (%s: hooks in a ROM copy at 0x%04X, tail in the undo buffer 0x%04X; %d patterns)'
        % (os.path.basename(sprites), patch.strategy, D5.ORG, U, patch.num_patterns))
    ok = True
    from nexclash.dizzy5 import verify5
    for r, _ in ans:
        t = time.time()
        v = verify5(prof, patch, r, stop=a.quick)
        ok &= v['passed']
        say('Verify    : %s %s (%.0fs)' % (os.path.basename(r), 'PASSED' if v['passed'] else 'FAILED', time.time() - t))
        say('            ' + ', '.join('%s %d' % kv for kv in sorted(v['stats'].items())))
        for e in v['examples']:
            say('            example: %s' % (e,))
    if not ok:
        say('RESULT    : sprite build FAILED verification - do not use; send this folder to the agent')
    _finish(out, name, rep)


def _boot(say, src, nex, patch, conv):
    """Simulated Next boot (nextboot.py): stub, alt ROM fill, tail -> registers, RAM, ROM view, paging."""
    from nexclash.nextboot import check
    snap, tail_addr, tail = conv[0], conv[1], conv[2]
    try:
        bad = check(nex, src, patch, (tail_addr, tail_addr + len(tail)))
    except Exception as e:          # noqa: BLE001 - report, do not hide
        bad = [('boot simulation error', str(e))]
    say('Boot      : simulated stub%s + tail: %s' % (' + alt ROM fill' if getattr(patch, 'altrom', None) else '',
        'OK (registers, RAM, ROM view, paging, $8C)' if not bad else 'MISMATCH %s' % bad[:3]))


EVIDENCE = os.path.join(HERE, 'nexclash', 'evidence.json')


def _fingerprint(mem, prof):
    import hashlib
    p = prof.get('plotter')
    if p is None:
        return None
    return hashlib.md5(bytes(mem[p:p + 512])).hexdigest()


def _evidence(fp):
    try:
        return json.load(open(EVIDENCE)).get(fp, {})
    except (OSError, ValueError):
        return {}


def _learn(fp, name, low, source):
    try:
        db = json.load(open(EVIDENCE))
    except (OSError, ValueError):
        db = {}
    e = db.setdefault(fp, {'game': name})
    if low < e.get('stack_low_water', 65536):
        e['stack_low_water'] = low
        e['source'] = source
    json.dump(db, open(EVIDENCE, 'w'), indent=1)


def _combine(ans):
    import copy
    c = dict(ans[0])
    for x in ans[1:]:
        c['rd'] = bytes(p | q for p, q in zip(c['rd'], x['rd']))
        c['wr'] = bytes(p | q for p, q in zip(c['wr'], x['wr']))
        c['rom_used'] |= x['rom_used']
        c['printer_buffer_touched'] |= x['printer_buffer_touched']
        c['stack_low_water'] = min(c['stack_low_water'], x['stack_low_water'])
    return c


DECISION_KEYS = ('stack_low_water', 'rom_used', 'printer_buffer_touched', 'pb_5b00_5b50_touched', 'altrom_hooks_read')


def _decisions(an):
    """The few analysis facts the plain / sprite builds depend on (build.plain, choose_tid_strategy):
    stored per game (docs/records) so a rebuild needs no recording (`auto --decisions FILE`)."""
    rd, wr = an['rd'], an['wr']
    return {'stack_low_water': an['stack_low_water'], 'rom_used': bool(an['rom_used']),
            'printer_buffer_touched': bool(an['printer_buffer_touched']),
            'pb_5b00_5b50_touched': any(rd[q] or wr[q] for q in range(0x5B00, 0x5B50)),
            'altrom_hooks_read': any(rd[B.ALTROM_HOOKS[0]:B.ALTROM_HOOKS[1]])}


def _an_from_decisions(d):
    """An analysis stand-in with exactly the stored facts (what build.plain and choose_tid_strategy read)."""
    missing = [k for k in DECISION_KEYS if k not in d]
    if missing:
        raise ValueError('decisions file lacks %s' % missing)
    rd, wr = bytearray(65536), bytearray(65536)
    if d['pb_5b00_5b50_touched']:
        rd[0x5B00] = 1
    if d['altrom_hooks_read']:
        rd[B.ALTROM_HOOKS[0]] = 1
    return {'rd': rd, 'wr': wr, 'stack_low_water': d['stack_low_water'], 'rom_used': d['rom_used'],
            'printer_buffer_touched': d['printer_buffer_touched']}


def _write_decisions(out, name, an, extra=None):
    d = dict(_decisions(an), **(extra or {}))
    json.dump(d, open(os.path.join(out, name + '_decisions.json'), 'w'), indent=1)
    return d


def _finish(out, name, rep):
    rep.append('')
    rep.append('Hardware checklist: starts; player visible and animating; hidden in boxes/room changes;')
    rep.append('title music unchanged. Problems: record an RZX (Fuse, autosave OFF) and send it.')
    open(os.path.join(out, name + '_report.txt'), 'w').write('\n'.join(rep) + '\n')
    print('Output    : %s' % out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for cmd in ('auto', 'patch', 'new'):
        p = sub.add_parser(cmd); p.add_argument('z80'); p.add_argument('--rzx', action='append')
        p.add_argument('--no-record', action='store_true'); p.add_argument('-o', '--out')
        p.add_argument('--quick', type=int, help='analyse/verify only the first N frames of each recording')
        p.add_argument('--strategy', choices=B.STRATEGIES,
                       help='patch memory: altrom (default where proven), printer or slot1 (reproduce old builds)')
        rec_args(p)
        p.add_argument('--ink', help="rainbow engine: sprite ink colour (white, black, blue, #RRGGBB)")
        p.add_argument('--outline', help="rainbow engine: mask-only pixels (black, blue, transparent, #RRGGBB)")
        p.add_argument('--class-colours', help='rainbow engine: JSON {"pages": {"D6": 1}, "palettes": {"1": {"ink": "#00FF00"}}}')
        p.add_argument('--allow-60hz', action='store_true', help='do not force 50 Hz video (outputs then differ from the verified MD5s)')
        p.add_argument('--decisions', help='rebuild from stored build decisions (docs/records); no recording, no verification')
    p = sub.add_parser('contribute'); p.add_argument('name', help='game name (zip name)')
    p.add_argument('--report', action='append', help='nexclash report(s) to include (GAME_report.txt)')
    p.add_argument('--note', help='one line for the maintainers'); p.add_argument('-o', '--output')
    p = sub.add_parser('identify'); p.add_argument('z80')
    p = sub.add_parser('record'); p.add_argument('z80'); p.add_argument('-o', '--output'); rec_args(p)
    p = sub.add_parser('convert'); p.add_argument('z80'); p.add_argument('--rzx', action='append'); p.add_argument('-o', '--output')
    p.add_argument('--tail', type=lambda v: int(v, 0), help='start-up tail address (128K: must end below 0xC000)')
    p.add_argument('--allow-60hz', action='store_true', help='do not force 50 Hz video')
    p = sub.add_parser('verify'); p.add_argument('z80'); p.add_argument('--rzx', action='append', required=True)
    p.add_argument('--allow-60hz', action='store_true', help='do not force 50 Hz video')
    p.add_argument('--strategy', choices=B.STRATEGIES)
    p = sub.add_parser('rzx'); p.add_argument('action', choices=['info', 'merge', 'strip']); p.add_argument('files', nargs='+')
    p.add_argument('-o', '--output')
    for cmd in ('inspect', 'scan', 'isr', 'cost', 'preview'):
        p = sub.add_parser(cmd); p.add_argument('z80')
        if cmd == 'inspect':
            continue
        p.add_argument('--rzx', action='append', help='recording(s) to play (default: free run)')
        p.add_argument('--frames', type=int, help='free run: frames (default 500)')
        p.add_argument('--keys', help='free run: key schedule, e.g. "5-14:SPACE; 30-:N" (K:LEFT... = Kempston)')
        p.add_argument('--stop', type=int, help='RZX: stop after N frames')
        if cmd == 'scan':
            p.add_argument('--range', action='append', help='LO-HI or bankN:0xC000-0xFFFF (repeatable)')
            p.add_argument('--after', type=lambda v: int(v, 0), help='count only once PC reaches this address')
            p.add_argument('--writers', action='store_true', help='per --range: the instructions that write / read it, with counts')
        if cmd == 'cost':
            p.add_argument('--at', type=lambda v: int(v, 0), required=True, help='routine entry address')
            p.add_argument('--group', choices=['A', 'BC', 'DE', 'HL', 'IX', 'IY'], help='break down by register at entry')
        if cmd == 'preview':
            p.add_argument('--at', help='frames to show, e.g. 100,600,1200 (default: 8 evenly spaced)')
            p.add_argument('--every', type=int, help='a shot every N frames (max 24)')
            p.add_argument('--plot', action='append', type=lambda v: int(v, 0), help='plot routine entry: colour what it draws, per caller (repeatable)')
            p.add_argument('--buffer', help='back buffer ADDR:STRIDE:LINES (e.g. 0x5B00:32:128) drawn next to the screen')
            p.add_argument('-o', '--out', default='preview.png', help='contact sheet (PNG)')
    a = ap.parse_args()
    if getattr(a, 'allow_60hz', False):
        zt.ALLOW_60HZ = True
        print('Video     : --allow-60hz: 50 Hz is NOT forced; the .nex MD5s differ from the verified builds')
    if a.cmd == 'inspect':
        from nexclash import snapinfo
        print(snapinfo.report(a.z80))
    elif a.cmd == 'scan':
        from nexclash import memscan
        print(memscan.scan(a.z80, a.rzx, a.frames, a.keys, a.range, a.stop, a.after, a.writers)[0])
    elif a.cmd == 'isr':
        from nexclash import isrinfo
        print(isrinfo.isr(a.z80, a.rzx, a.frames, a.keys, a.stop)[0])
    elif a.cmd == 'cost':
        from nexclash import drawcost
        print(drawcost.cost(a.z80, a.at, a.rzx, a.frames, a.keys, a.stop, a.group)[0])
    elif a.cmd == 'preview':
        from nexclash import preview
        buf = tuple(int(x, 0) for x in a.buffer.split(':')) if a.buffer else None
        at = [int(x) for x in a.at.split(',')] if a.at else None
        print(preview.preview(a.z80, a.rzx, a.out, at, a.every, a.plot, buf, a.frames, a.keys, a.stop)[0])
    elif a.cmd == 'auto':
        cmd_auto(a)
    elif a.cmd in ('patch', 'new', 'contribute'):
        from nexclash import userflow as U
        sys.exit(U.cmd_patch(a, cmd_auto) if a.cmd == 'patch' else U.cmd_new(a, cmd_auto) if a.cmd == 'new'
                 else U.cmd_contribute(a))
    elif a.cmd == 'identify':
        prof = identify(Snapshot.get(a.z80).memory[0:65536])
        print(json.dumps(prof, indent=1))
    elif a.cmd == 'record':
        out = a.output or os.path.splitext(a.z80)[0] + '_auto.rzx'
        print(do_record(a, a.z80, out))
    elif a.cmd == 'convert':
        from nexclash.analyse import analyse
        out = a.output or os.path.splitext(a.z80)[0] + '.nex'
        try:
            if a.tail is not None:
                zt.convert(a.z80, out, a.tail, True, quiet=True)
                print('tail at 0x%04X (requested) ->' % a.tail, out)
                return
            s = Snapshot.get(a.z80)
            an = _combine([analyse(None, r, s.sp) for r in a.rzx]) if a.rzx else None
            print(B.plain(a.z80, out, an), '->', out)
        except ValueError as e:
            sys.exit('Error: %s' % e)
    elif a.cmd == 'verify':
        a.no_record, a.out, a.quick = True, None, None
        a.start = a.script = a.keys = None
        a.strategy = getattr(a, 'strategy', None)
        cmd_auto(a)
    elif a.cmd == 'rzx':
        if a.action == 'info':
            for f in a.files:
                print(rzxmod.info(f))
        elif a.action == 'strip':
            out = a.output or os.path.splitext(a.files[0])[0] + '_stripped.rzx'
            print('dropped %d autosave snapshot(s)' % rzxmod.strip(a.files[0], out))
            print(rzxmod.info(out))
        else:
            rzxmod.merge(a.files, a.output or 'merged.rzx')
            print(rzxmod.info(a.output or 'merged.rzx'))


if __name__ == '__main__':
    main()
