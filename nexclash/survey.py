"""Stage 0 (PLAYBOOK): one command that does the mechanical part of a new game before any design work.

    python -m nexclash.survey GAME.z80 [--rzx R ...] [--stop N] [--frames N --keys K] [--full] [-o DIR]

Known engines return survey.md/json with recognition only; --full opts into all steps below.
Writes DIR (default <game>_survey/ next to the snapshot): survey.md (one page: read it first),
survey.json (the raw numbers), preview.png (what each plot routine draws, per caller), <game>.nex
(the plain conversion). Steps:
  1. snapshot check (`inspect`), engine identification (engines.py detectors + identify),
  2. plain conversion with the tail placement of `convert` (48K: proven by the access analysis) and
     the simulated boot (nextboot.check),
  3. ONE pass over the recording(s) with three trackers: memory access + screen writers (`scan`),
     the interrupt handler (`isr`), and the plot routines (below),
  4. a preview pass for the top plot routines (`preview --plot`).
Plot routines: every screen write is put on the innermost CALL (or interrupt) that is running - a
shadow call stack, so a game that drops return addresses or uses SP as a data pointer can blur it.
Per routine: screen bytes written, calls, callers seen, T-states per call (interrupts included),
the routines that call it, block-copy writes (LDIR / LDI / PUSH: a back buffer copy).
Coverage gate: every CALL to a top plot routine found in the 64K view (byte pattern CD/C4/.. nn,
so some can be data) against the callers the recording reached. A site in code that ran but not
reached = a path the recording missed; ask for a recording that reaches it before stage 1.

Game-independent. Reuses memscan.Scanner / isrinfo.IsrTracker and their report() unchanged; this
module is no game's dependency (docs/records), so changing it re-verifies nothing.
"""
import argparse
import collections
import json
import os
import statistics
import sys

LONG, FIRST_LOOK = 20000, 15000        # frames: warn above LONG, suggest --stop FIRST_LOOK

CALLS = {0xCD} | {0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC}
JPS = {0xC3} | {0xC2, 0xCA, 0xD2, 0xDA, 0xE2, 0xEA, 0xF2, 0xFA}
BLOCK = {(0xED, 0xB0): 'LDIR', (0xED, 0xB8): 'LDDR', (0xED, 0xA0): 'LDI', (0xED, 0xA8): 'LDD'}
PUSHES = {0xC5, 0xD5, 0xE5, 0xF5}


class PlotTracker:
    """Shadow call stack; screen writes per innermost routine; calls, callers, T per call."""

    def __init__(self):
        self.sim = None
        self.stack = []                       # [target, ret, sp, caller_pc, t0]
        self.pending = None                   # (pc, target, sp) of a CALL about to run
        self.pix = collections.Counter()      # routine -> pixel bytes written (bitmap 0x4000-0x57FF)
        self.attr = collections.Counter()     # routine -> attribute bytes written
        self.block = collections.Counter()    # routine -> screen bytes written by LDIR/LDI/PUSH...
        self.calls = collections.defaultdict(collections.Counter)    # target -> caller pc -> calls
        self.parents = collections.defaultdict(collections.Counter)  # target -> enclosing routine -> calls
        self.tcost = collections.defaultdict(list)                   # target -> T per call (sampled)
        self.frames_active = collections.defaultdict(set)
        self.src = collections.defaultdict(collections.Counter)      # screen-writing routine -> 64-byte granule -> data reads
        self.frame = 0
        self.T = 0                            # own T-state count (the replay resets its counter per frame)

    def on_sim(self, sim):
        self.sim = sim
        self.stack, self.pending = [], None

    def on_frame(self, n):
        self.frame = n

    def on_interrupt(self, sim, prev_pc):
        R = sim.registers                     # R[24] = where it returns (as isrinfo / drawcost)
        self.stack.append(['ISR', R[24], R[12], R[24], self.T])

    def _pop(self, pc, sp, R):
        st = self.stack
        while st and sp > st[-1][2]:                      # unwound some other way: drop the frame
            st.pop()
        if st and sp == st[-1][2] and (pc == st[-1][1] or (st[-1][0] == 'ISR' and pc == (st[-1][1] + 1) & 0xFFFF)):
            # an interrupt taken at a HALT returns to the instruction after it
            f = st.pop()
            if f[0] != 'ISR':
                c = self.tcost[f[0]]
                if len(c) < 4000:
                    c.append(self.T - f[4])

    def before(self, pc):
        R = self.sim.registers
        sp = R[12]
        p = self.pending
        if p is not None:
            self.pending = None
            if pc == p[1] and sp == (p[2] - 2) & 0xFFFF:
                parent = self.stack[-1][0] if self.stack else 'top'
                self.calls[p[1]][p[0]] += 1
                self.parents[p[1]][parent] += 1
                self.stack.append([p[1], (p[0] + 3) & 0xFFFF, p[2], p[0], self.T])
                # The entry instruction can itself CALL (R-Type: 8979 -> 8842).
                # Track it too, or its writes get charged to the outer routine.
        if self.stack:
            self._pop(pc, sp, R)
        m = self.sim.memory
        op = m[pc]
        if op in CALLS:
            self.pending = (pc, m[(pc + 1) & 0xFFFF] | m[(pc + 2) & 0xFFFF] << 8, sp)

    def after(self, pc, dt):
        self.T += dt

    def on_read(self, a, pc, mem):
        if a < 0x5B00 or pc <= a <= pc + 3 or not self.stack:      # ROM, the screen, the instruction's own bytes
            return
        r = self.stack[-1][0]
        if r in self.frames_active and not -64 < a - self.sim.registers[12] < 64:   # screen writers; not the stack
            self.src[r][a >> 6] += 1

    def on_write(self, a, v, pc, mem):
        if 0x4000 <= a < 0x5B00:
            pass
        elif a >= 0xC000 and getattr(mem, 'o7ffd', 0) & 7 == 7 and a < 0xDB00:
            a -= 0x8000                                    # shadow screen (bank 7) seen at 0xC000
        else:
            return
        r = self.stack[-1][0] if self.stack else 'top'
        (self.pix if a < 0x5800 else self.attr)[r] += 1
        self.frames_active[r].add(self.frame)
        op = mem[pc]
        if op in PUSHES or (op == 0xED and (0xED, mem[(pc + 1) & 0xFFFF]) in BLOCK):
            self.block[r] += 1


class Multi:
    """Fan the simrun hooks out to several trackers (one pass instead of one per command)."""

    def __init__(self, *ts):
        for name in ('on_sim', 'before', 'after', 'on_read', 'on_write', 'on_interrupt', 'on_frame'):
            fs = [getattr(t, name) for t in ts if hasattr(t, name)]
            if fs:
                setattr(self, name, (lambda fs: lambda *x: [f(*x) for f in fs])(fs))


def static_sites(mem, target, ran):
    """CALL / JP byte patterns to `target` in the 64K view; ran(addr) = code ran near it."""
    lo, hi = target & 0xFF, target >> 8
    out = []
    for a in range(0x4000, 0xFFFE):
        if mem[a + 1] == lo and mem[a + 2] == hi:
            op = mem[a]
            if op in CALLS or op in JPS:
                out.append((a, 'CALL' if op in CALLS else 'JP', ran(a)))
    return out


def _spans(counter, top=3):
    """64-byte granules -> the largest contiguous spans [(lo, hi, reads)]."""
    out, cur = [], None
    floor = max(counter.values(), default=0) / 20          # a routine left on the shadow stack reads everything a little
    for g in sorted(g for g in counter if counter[g] >= floor):
        if cur and g == cur[1] + 1:
            cur[1], cur[2] = g, cur[2] + counter[g]
        else:
            cur = [g, g, counter[g]]
            out.append(cur)
    return [(lo << 6, (hi << 6) + 63, n) for lo, hi, n in sorted(out, key=lambda c: -c[2])[:top]]


def findings(pt, it, n, routines):
    """Derived from the counts (no disassembly): rendering model, pacing, roles. -> (lines, dict).
    Heuristics: each line says what it rests on; check before relying on it (PLAYBOOK 2)."""
    out, js = [], {}
    ints = [r for r in routines if isinstance(r['routine'], int)]
    tot = sum(pt.pix.values()) or 1
    lead = max(ints, key=lambda r: r['pixel_bytes'], default=None)
    if lead and lead['pixel_bytes']:
        share, per = lead['pixel_bytes'] / tot, lead['pixel_bytes'] / max(1, lead['calls'])
        if share >= 0.6 and lead['block_copy_bytes'] >= 0.6 * lead['pixel_bytes']:
            js['model'] = 'back buffer, block copy to the screen'
        elif share >= 0.6 and 7.5 <= per <= 8.5:
            js['model'] = 'cell copier (8 pixel bytes per call): figures are composed off screen, as cells or in a buffer'
        elif share >= 0.6:
            js['model'] = 'one routine draws most pixels (%d bytes per call): a copier, or the only plotter' % per
        else:
            js['model'] = 'several routines draw to the screen directly'
        out.append('- Rendering model: %s. Basis: %s writes %d%% of the pixel bytes, %d%% of them by block copy.'
                   % (js['model'], _h(lead['routine']), 100 * share, 100 * lead['block_copy_bytes'] / lead['pixel_bytes']))
        if share >= 0.6:
            lead['role'] = 'screen copier'
            js['sources'] = {}
            for r in [lead['routine']] + [int(k) for k in lead['called_from_routines'] if k.isdigit()]:
                sp = _spans(pt.src.get(r, {}))
                if sp:
                    js['sources'][str(r)] = [[lo, hi, c] for lo, hi, c in sp]
                    out.append('  - %s reads its data from %s: the buffer / cell map / graphics it copies. Next: '
                               '`scan --range LO-HI --writers` on the largest (who composes it), not the preview below.'
                               % (_h(r), ', '.join('0x%04X-0x%04X (x%d)' % x for x in sp)))
    for r in ints:
        if 'role' not in r:
            r['role'] = 'attribute writer' if not r['pixel_bytes'] and r['attr_bytes'] else 'plotter'
        if r['T_max'] and r['T_max'] > 20 * 69888:
            r['role'] = 'main loop (attribution blurred)'
            out.append('- %s: T max %d is over 20 frames - the main loop or a wait inside it; its row is the '
                       'shadow call stack blurring (check with `cost --at`), not a plotter.' % (_h(r['routine']), r['T_max']))
    js['interrupts_accepted'] = it.count
    if it.count == 0:
        js['pacing'] = 'no interrupts'
        out.append('- Pacing: no interrupt was accepted in %d frames: the game runs with interrupts off, so nothing '
                   'syncs it to the frame and hook time changes game speed (PLAYBOOK 4 "no frame sync"; card '
                   'detect.pacing-structure).' % n)
    else:
        js['pacing'] = 'interrupts on'
        out.append('- Pacing: %d interrupts accepted in %d frames (handler below). Whether the game waits for '
                   'them (HALT / flag) is card detect.pacing-structure.' % (it.count, n))
    return out, js


def lessons(js, top=10):
    """Lines for survey.md: the shared lessons (docs/kb/lessons) that fit what this survey measured, best first.
    [] when this copy has no tools/knowledge.py or no lessons (the survey stands without them)."""
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools', 'knowledge.py')
    try:
        spec = importlib.util.spec_from_file_location('nexclash_knowledge', path)
        K = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(K)
        facts = K.game_facts(js)
        got, n = K.briefing(facts, K.shared(), top)
    except Exception:                                       # noqa: BLE001 - never fail a survey for its reading list
        return []
    if not got:
        return []
    return (['## Shared lessons that fit (%s)' % (', '.join('%s %s' % kv for kv in sorted(facts.items())) or 'no facts measured'),
             'What other games learned, best supported first: leads to check, not facts about this game. '
             '%d of %d that fit; more: `python tools/knowledge.py lessons --facts %s` (or `lessons WORD`); '
             'evidence: `lessons --show ID`.' % (len(got), n, 'SURVEY_DIR/survey.json')]
            + ['- %s: %s' % (x['id'], x['claim']) for x in got] + [''])


def _md5(path):
    import hashlib
    return hashlib.md5(open(path, 'rb').read()).hexdigest() if os.path.exists(path) else None


def _h(a):
    return '%d (0x%04X)' % (a, a) if isinstance(a, int) else str(a)


def survey(z80, rzx=None, out=None, stop=None, frames=None, keys=None, top=6, log=print, full=False, fresh=False):
    from skoolkit.snapshot import Snapshot
    from . import snapinfo, memscan, isrinfo, preview as P, build as B, z80tonex as zt, nextboot
    from .simrun import run
    from .identify import identify
    from .engines import find
    name = os.path.splitext(os.path.basename(z80))[0]
    out = out or os.path.join(os.path.dirname(os.path.abspath(z80)), name + '_survey')
    os.makedirs(out, exist_ok=True)
    inputs = {'z80': _md5(z80), 'rzx': [_md5(r) for r in rzx or []],
              'args': [stop, frames, keys, top, bool(full)]}
    old_js, old_md = os.path.join(out, 'survey.json'), os.path.join(out, 'survey.md')
    if not fresh and os.path.exists(old_js) and os.path.exists(old_md):
        try:
            js = json.load(open(old_js))
        except ValueError:
            js = {}
        if js.get('inputs') == inputs:                      # same files, same arguments: minutes saved
            log('survey: reusing %s (same snapshot, recordings and arguments; --fresh runs it again)' % old_md)
            return open(old_md).read(), js
    md, js = [], {'game': name, 'inputs': inputs}
    say = md.append
    s = Snapshot.get(z80)
    is128 = len(s.ram(-1)) == 0x20000
    js['machine'] = '128K' if is128 else '48K'
    say('# Survey: %s (%s)' % (name, '128K' if is128 else '48K'))
    say('Read this first (PLAYBOOK stage 0). Raw numbers: survey.json. Commands to dig further: PLAYBOOK 2-3.')
    say('')
    say('## Snapshot (inspect)')
    say('```\n' + snapinfo.report(z80) + '\n```')

    # engine
    eng = find(s, argparse.Namespace(engine=None))
    prof = identify(s.memory[0:65536]) if not is128 else {'engine': None}
    js['engine'] = eng.__name__.split('.')[-1] if eng else prof.get('engine')
    say('## Engine')
    if eng:
        say('KNOWN dedicated engine `%s`: `python nexclash.py auto %s --rzx R --no-record` builds it; no new engine needed.'
            % (js['engine'], os.path.basename(z80)))
    elif prof.get('engine') not in (None, 'unknown'):
        say('Generic engine `%s` (identify): `python nexclash.py auto` builds it.' % prof['engine'])
    else:
        say('Unknown: no detector in nexclash/engines.py and no TID / Dizzy 1 signature -> stage 1 (a new engine).')
    say('')

    if js['engine'] not in (None, 'unknown') and not full:
        js['mode'] = 'recognition-only'
        say('Recognition only: no recording replay, conversion or verification was run.')
        say('Use --full to investigate this known game; use auto to build and check it.')
        text = '\n'.join(md) + '\n'
        open(os.path.join(out, 'survey.md'), 'w').write(text)
        json.dump(js, open(os.path.join(out, 'survey.json'), 'w'), indent=1)
        return text, js
    js['mode'] = 'full'

    # recordings
    rz = []
    if rzx:
        from skoolkit.rzxplay import parse_rzx
        from . import rzx as RZ
        say('## Recordings')
        for r in rzx:
            blocks = parse_rzx(r)
            nsnap = sum(1 for b in blocks if isinstance(b.obj, Snapshot))
            nfr = sum(int.from_bytes(b.data[5:9], 'little') for b in blocks if b.data[0] == 0x80)
            if nfr > LONG and not stop:
                msg = ('%s: %d frames (%d min of play; the checklist asks for 3-5): the survey replays it twice, '
                       'about %d min. First look: --stop %d.' % (os.path.basename(r), nfr, nfr // 3000, nfr // 3000, FIRST_LOOK))
                log('survey: WARNING ' + msg)
                say('- WARNING ' + msg)
            if nsnap > 1:          # analyse() (the plain build's tail proof) desyncs on autosave snapshots
                r2 = os.path.join(out, os.path.splitext(os.path.basename(r))[0] + '_stripped.rzx')
                RZ.strip(r, r2)
            say('- %s: %s' % (os.path.basename(r), 'autosave snapshots: %d, stripped -> %s' % (nsnap - 1, os.path.basename(r2))
                              if nsnap > 1 else 'no autosave snapshots'))
            rz.append(r2 if nsnap > 1 else r)
        say('')

    # plain conversion + boot
    log('survey: plain conversion ...')
    plain = os.path.join(out, name + '.nex')
    an, note = None, ''
    if rz:              # 128K too: below 0xC000 (where a tail must end) banks 5 and 2 never move, so 'rd'/'wr' are exact there
        from .analyse import analyse, merge_scans
        ans = [analyse(None, r, s.sp, stop=stop) for r in rz]
        an = dict(ans[0])
        for x in ans[1:]:
            merge_scans(an, x)
            an['rom_used'] |= x['rom_used']
            an['stack_low_water'] = min(an['stack_low_water'], x['stack_low_water'])
    elif is128:
        note = ' (128K, no recording: tail not proven - prove it with `scan --range`, PLAYBOOK 1)'
    cap, orig = {}, zt.convert

    def conv(*a, **k):
        cap['c'] = orig(*a, **k)
        return cap['c']
    zt.convert = conv
    try:
        where = B.plain(z80, plain, an, log=lambda *x: None)
    except ValueError as e:
        where = 'FAILED: %s' % e
    finally:
        zt.convert = orig
    boot = 'not run'
    if is128:
        boot = "not run: nextboot.check models 48K start-up only (128K engines bring their own boot check, e.g. midres.boot_check)"
    elif 'c' in cap:
        c = cap['c']
        try:
            bad = nextboot.check(plain, z80, None, (c[1], c[1] + len(c[2])))
            boot = 'OK (registers, RAM, ROM view, paging)' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]
        except Exception as e:                              # noqa: BLE001 - report, do not hide
            boot = 'boot simulation error: %s' % e
    js['plain'] = {'file': os.path.basename(plain), 'tail': where, 'boot': boot}
    say('## Plain conversion')
    say('- %s: %s%s; simulated boot: %s. The user tests it on the Next with the stage-1 question.'
        % (os.path.basename(plain), where, note, boot))
    say('')

    # the combined pass
    log('survey: analysis pass (memory, screen writers, interrupts, plot routines) ...')
    screen = '0x4000-0x5AFF'
    watch = [(screen, set(memscan.parse_range(screen, is128)))]
    sc, it, pt = memscan.Scanner(None, watch), isrinfo.IsrTracker(), PlotTracker()
    n = run(z80, rz or None, Multi(sc, it, pt), frames=frames, keys=keys, stop=stop)
    js['frames'] = n
    mem_txt = memscan.report(sc, n, rz or None, keys, None, None, is128, None)[0]
    scr_txt = memscan.report(sc, n, rz or None, keys, [screen], None, is128, watch)[0]
    isr_txt = isrinfo.report(it, n, z80, rz or None, keys)[0]

    # plot routines
    ran = lambda a: any(sc.flags[i] & memscan.EXEC for i in range(max(0, a - 24), min(0xC000, a + 24)) if i < 0xC000)
    rank = sorted(set(pt.pix) | set(pt.attr), key=lambda r: -(pt.pix[r] + pt.attr[r]))
    rows, gaps, routines = [], 0, []
    mem = pt.sim.memory if pt.sim is not None else s.memory
    for r in rank[:top]:
        calls = sum(pt.calls[r].values()) if r not in ('top', 'ISR') else 0
        tc = pt.tcost.get(r, [])
        info = {'routine': r, 'pixel_bytes': pt.pix[r], 'attr_bytes': pt.attr[r], 'block_copy_bytes': pt.block[r],
                'calls': calls, 'frames_active': len(pt.frames_active[r]),
                'callers_seen': {str(k): v for k, v in pt.calls[r].most_common()} if isinstance(r, int) else {},
                'called_from_routines': {str(k): v for k, v in pt.parents[r].most_common(3)} if isinstance(r, int) else {},
                'T_median': int(statistics.median(tc)) if tc else None, 'T_max': max(tc) if tc else None}
        if isinstance(r, int) and r >= 0x4000:
            st = static_sites(mem, r, ran)
            seen = set(pt.calls[r])
            info['call_sites'] = [{'at': a, 'kind': k, 'code_ran_near': g, 'reached': a in seen} for a, k, g in st]
            miss = [x for x in info['call_sites'] if x['kind'] == 'CALL' and not x['reached'] and x['code_ran_near']]
            info['not_reached'] = [x['at'] for x in miss]
            gaps += len(miss)
        routines.append(info)
        cov = ''
        if 'call_sites' in info:
            nc = [x for x in info['call_sites'] if x['kind'] == 'CALL']
            cov = '%d/%d CALL sites reached%s' % (sum(x['reached'] for x in nc), len(nc),
                                                  ('; NOT reached (code ran nearby): ' + ', '.join(_h(a) for a in info['not_reached'][:6]))
                                                  if info['not_reached'] else '')
            nj = sum(1 for x in info['call_sites'] if x['kind'] == 'JP')
            if nj:
                cov += '; %d JP site(s) (not tracked)' % nj
        rows.append('| %s | %d / %d%s | %d | %d | %s | %s | %s |' % (
            _h(r) if isinstance(r, int) else r + (' (outside any CALL)' if r == 'top' else ' (interrupt handler)'),
            pt.pix[r], pt.attr[r], ' (%d block copy)' % pt.block[r] if pt.block[r] else '', calls,
            len(pt.calls[r]),
            '%s / %s' % (info['T_median'], info['T_max']) if tc else '-',
            ', '.join(_h(k) if isinstance(k, int) else k for k in pt.parents[r]) if isinstance(r, int) else '-',
            cov or '-'))
    js['routines'] = routines
    js['coverage_gaps'] = gaps
    from . import kb
    try:
        dis = kb._disassembler(mem)
        for info in routines:
            if isinstance(info['routine'], int) and info['routine'] >= 0x4000:
                info['fingerprint'] = kb.fingerprint(mem, info['routine'], dis)
    except Exception as e:                                  # noqa: BLE001 - the survey stands without them
        log('survey: no fingerprints (%s)' % e)
    f_lines, js['findings'] = findings(pt, it, n, routines)
    known = kb.match(routines, z80=inputs['z80'])
    say('## Recording and coverage')
    say('- %d frames analysed%s.' % (n, ' (free run, keys: %s)' % (keys or 'none') if not rz else ''))
    say('- GATE: %s' % ('OK - every CALL site to the top plot routines in code that ran was reached'
                         if not gaps else 'CHECK - %d CALL site(s) to these routines, in code that ran, were never reached '
                         '(table below). For a FIGURE plotter that is a path the recording missed: ask the user for a '
                         'recording that reaches it (docs/RECORDING_CHECKLIST.md) before stage 1. For a text / score '
                         'printer it usually is a message that did not come up: say so in games/<game>.md.' % gaps))
    say('')
    say('## Findings (derived from the counts - heuristics, each with its basis)')
    md.extend(f_lines)
    for sc_, mine, game, theirs, role in known[:6]:
        say('- Known code: %s resembles %s %s in docs/kb/games/%s.json (%.2f)%s - read games/%s.md before designing.'
            % (_h(mine), _h(theirs), ('(%s)' % role) if role else '', game, sc_, '' if sc_ < 1 else ' = same code', game))
    if not known:
        say('- Known code: no routine resembles a game in docs/kb (`python -m nexclash.kb list`).')
    say('- At stage end: `python -m nexclash.kb add %s --game <game>` (docs/kb: the next game starts from this one).'
        % os.path.basename(out))
    say('')
    md.extend(lessons(js))
    say('## Screen writers by routine (innermost CALL running at the write)')
    say('| Routine | pixel / attr bytes | calls | callers seen | T per call median / max | called from | coverage |')
    say('|---|---|---|---|---|---|---|')
    md.extend(rows)
    say('Block copies (LDIR / LDI / PUSH) into the screen = probably a back buffer: `scan --range BUF --writers` '
        'on its source (PLAYBOOK 2). A routine in ROM (< 0x4000) is the ROM printing text.')
    say('')

    # preview
    plots = [r for r in rank[:top] if isinstance(r, int) and r >= 0x4000][:6]
    if n >= 8:
        log('survey: preview pass ...')
        step = max(1, n // 8)
        at = list(range(step, n + 1, step))[:8]
        try:
            ptxt = P.preview(z80, rz or None, os.path.join(out, 'preview.png'), at, None, plots or None, None,
                             frames or (n if not rz else None), keys, n)[0]
        except Exception as e:                              # noqa: BLE001
            ptxt = 'preview failed: %s' % e
        say('## Preview (preview.png: screen at frames %s, what each plot routine draws per caller, tinted per routine: not game colours)' % ','.join(map(str, at)))
        say('```\n' + '\n'.join(ptxt.split('\n')[:14]) + '\n```')
        say('')
    say('## Screen writers (scan --writers)')
    say('```\n' + scr_txt + '\n```')
    say('## Memory (scan: free memory for hook state, stack low-water)')
    say('```\n' + '\n'.join(mem_txt.split('\n')[:28]) + '\n```')
    say('## Interrupt handler (isr: what hooks must keep intact)')
    say('```\n' + isr_txt + '\n```')
    text = '\n'.join(md) + '\n'
    open(os.path.join(out, 'survey.md'), 'w').write(text)
    json.dump(js, open(os.path.join(out, 'survey.json'), 'w'), indent=1, default=str)
    return text, js


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('z80')
    ap.add_argument('--rzx', action='append', help='recording(s) (repeatable); none = a free run')
    ap.add_argument('--stop', type=int, help='RZX: stop after N frames')
    ap.add_argument('--frames', type=int, help='free run: frames (default 500)')
    ap.add_argument('--keys', help='free run: key schedule, e.g. "5-14:SPACE; 30-:N"')
    ap.add_argument('--fresh', action='store_true', help='run again even when survey.json has the same inputs')
    ap.add_argument('--full', action='store_true', help='analyse even a recognised game (default: recognition only)')
    ap.add_argument('--top', type=int, default=6, help='plot routines to report (default 6)')
    ap.add_argument('-o', '--out', help='output folder (default <game>_survey next to the snapshot)')
    a = ap.parse_args(argv)
    text, js = survey(a.z80, a.rzx, a.out, a.stop, a.frames, a.keys, a.top, log=lambda m: print(m, file=sys.stderr), full=a.full,
                      fresh=a.fresh)
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
