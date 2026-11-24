"""Load an nxsuite result file (NXSUITE.TXT) into the repository's hardware results (GPL-3.0-or-later, part of nexclash).

    python tools/hwtests/intake.py NXSUITE.TXT [--board NAME] [--platform board|"JNext 1.3.0"|...] [--out DIR]
                                   [--dry-run]
    python tools/hwtests/intake.py --compare A.json B.json
    python tools/hwtests/intake.py --selfcheck

Reads the file (format: tools/hwtests/README.md "nxsuite", spec section 2), REFUSES one that is malformed or
truncated (no END line, wrong line count or CRC-16, an unknown record, an unknown test id, a status it does not
know), and writes docs/kb/hardware/<board>-<core>.json: one file per board + core, a re-run of the same pair
replaces it and counts the runs. Then prints a report, one line per claim of nxsuite_claims.json:
CONFIRMED / DISPROVED / MEASURED value +- spread / CHOICE word / NOT ANSWERED (skipped, hung, operator question
pending, not built), with the sources the claim names (lessons, doc lines) so a maintainer sees what to check
or correct. It never edits lessons or docs: applying a result is a later, reviewed step.

Statuses: PASS / FAIL decided on the machine; INFO a number or a choice for this tool to report; SKIP (why=);
HANG-GUARD the machine stopped in this test (the next start marked it); OPERATOR an answer typed at a
question screen (key=, means=); PENDING-OPERATOR a question not answered yet; VISUAL / VISUAL-SHOWN (kept
for photographs). A file can hold several sessions (each starts with an `H suite=` line); for a test the
last line written wins.

Passes: one file can hold several passes (RUN ALL, then a group alone, ...). A pass starts at a `P pass=`
line (builds from 2026-11-23 on), at a new `H suite=` session, or - for older files - where a group starts
again that the current pass already ran, or
any group that does not follow the previous one in table order. Every test keeps all its records; the verdict uses the LATEST
pass that ran it, and the report lists every test whose passes disagree (status, value or an extra), so
passes are never mixed silently.

Parts: a session may write more than the 64 KB buffer. The program then writes the buffer to the next free
NXSUITE.nnn (a "part", with its own END line) and NXSUITE.TXT goes on with "C part=nnn src=<build>"
after its first line. Give NXSUITE.TXT: the intake follows the C lines back through the parts beside it
(every part must check), joins them and reads them as one file. A missing part is REFUSED. Older files
of another build that the program kept as parts are not read unless named. An "X truncated lost=<n>"
record (bytes the program could not store) is reported as a WARNING and marked in the JSON ("truncated").

Platform: the program cannot tell a board from an emulator, so --platform says it: "board" (default) or the
emulator's name and exact version ("JNext 1.3.0", "CSpect 3.0.x"). Emulator results are written to
docs/kb/hardware/emulator/<platform>-<core>.json, apart from board results, and never count as hardware
evidence; --compare marks a board-vs-emulator comparison.

Sub-case claims: where a test's sub-cases answer different claims (Z01: zf.*), each claim is decided by its
own cases (SUBCLAIMS), not by the parent test's overall status.
"""
import argparse
import collections
import datetime
import hashlib
import io
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TABLE = os.path.join(HERE, 'nxsuite_claims.json')
OUTDIR = os.path.join(ROOT, 'docs', 'kb', 'hardware')
STATUSES = {'PASS', 'FAIL', 'INFO', 'SKIP', 'HANG-GUARD', 'VISUAL', 'VISUAL-SHOWN', 'OPERATOR', 'PENDING-OPERATOR'}
# multi-claim tests: the extra key that decides one of their claims (the test's own status decides the rest)
CLAIM_KEYS = {('S01', 'sys-launch-7ffd-unlocked'): 'p7ffd',
              # I13's PASS is the polled status; the time-constant claim is its choice= word
              ('I13', 'irq-ctc-time-constant'): 'choice',
              # N01 (nextbench table) is INFO; its DMA copy / fill rows at 3.5 MHz decide this claim
              ('N01', 'dma-correct-3m5'): 'dma35'}


# claim -> (parent test, case-name pattern, F bits to ignore: bits the docs call unsure for those cases)
SUBCLAIMS = {'z80n-func-suite': ('Z01', r'zf\.(?!LDPIRX)', 0),     # "all green except LDPIRX"
             'z80n-ldix-flags': ('Z01', r'zf\.LD[ID]R?X[0F]', 0),
             'z80n-ldpirx-fixed': ('Z01', r'zf\.LDPIRX', 0x28),     # NEXT_REGISTERS: LDPIRX F bits 5/3 unsure
             'z80n-jpc-flags': ('Z01', r'zf\.JPC', 0),
             'z80n-test-nf': ('Z01', r'zf\.TEST', 0)}


class Refused(Exception):
    pass


def crc16(data):
    """CRC-16/CCITT (poly $1021, init $FFFF), as nxsuite crcb."""
    c = 0xFFFF
    for b in data:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) if c & 0x8000 else c << 1
            c &= 0xFFFF
    return c


def load_table(path=TABLE):
    t = json.load(open(path, encoding='utf-8'))
    t['by_test'] = {x['id']: x for x in t['tests']}
    t['by_claim'] = {c['id']: c for c in t['claims']}
    t['prefixes'] = {x['sub_prefix']: x['id'] for x in t['tests'] if x.get('sub_prefix')}
    return t


def kv(fields, lineno):
    d = {}
    for f in fields:
        if '=' not in f:
            d[f] = True                 # a bare word (G ... start / end, H divmmc)
            continue
        k, v = f.split('=', 1)
        if not k:
            raise Refused('line %d: empty key in %r' % (lineno, f))
        d[k] = v
    return d


def checked_lines(data, check_crc=True):
    """bytes of one file -> its lines without the END line (first = "NXSUITE 1"). Raises Refused."""
    if b'\r' in data:
        raise Refused('CR bytes: the file must use LF line ends')
    try:
        text = data.decode('ascii')
    except UnicodeDecodeError:
        raise Refused('not ASCII')
    if not text.endswith('\n'):
        raise Refused('truncated: the last line has no LF')
    lines = text.split('\n')[:-1]
    if not lines or lines[0] != 'NXSUITE 1':
        raise Refused('first line is not "NXSUITE 1"')
    last = lines[-1]
    if not last.startswith('END '):
        raise Refused('truncated: no END line (the machine stopped while writing, or the copy is short)')
    end = kv(last.split()[1:], len(lines))
    body = text[:len(text) - len(last) - 1].encode('ascii')
    if str(len(lines) - 1) != end.get('lines'):
        raise Refused('END lines=%s, the file has %d lines before it' % (end.get('lines'), len(lines) - 1))
    want = end.get('crc16', '')
    if check_crc and want.upper() != '$%04X' % crc16(body):
        raise Refused('CRC-16 %s, computed $%04X: the file is damaged' % (want, crc16(body)))
    return lines[:-1]


def load_chain(path, check_crc=True, seen=None):
    """NXSUITE.TXT (or a part) -> (bytes of the joined file, [file names]). A file whose second line is
    "C part=nnn src=..." continues NXSUITE.nnn in the same folder."""
    seen = seen or set()
    ap = os.path.abspath(path)
    if ap in seen:
        raise Refused('the C lines go round in a circle at %s' % os.path.basename(path))
    seen.add(ap)
    try:
        lines = checked_lines(open(path, 'rb').read(), check_crc)
    except Refused as e:
        raise Refused('%s: %s' % (os.path.basename(path), e))
    if len(lines) < 2 or not lines[1].startswith('C '):
        return lines, [os.path.basename(path)]
    f = kv(lines[1].split()[1:], 2)
    part = f.get('part', '')
    if not re.fullmatch(r'\d{3}', part):
        raise Refused('%s line 2: C line without part=nnn' % os.path.basename(path))
    folder = os.path.dirname(ap)
    want = 'NXSUITE.%s' % part
    prev = next((os.path.join(folder, n) for n in os.listdir(folder) if n.upper() == want), None)
    if prev is None:
        raise Refused('%s continues %s, which is not beside it: copy every NXSUITE.* file back' % (
            os.path.basename(path), want))
    plines, names = load_chain(prev, check_crc, seen)
    psrc = next((kv(x.split()[1:], 0).get('src') for x in plines[1:3] if x.startswith(('H suite=', 'C '))), None)
    if f.get('src') != psrc:
        raise Refused('%s says src=%s, %s is src=%s' % (os.path.basename(path), f.get('src'), want, psrc))
    return plines + lines[2:], names + [os.path.basename(path)]


def parse(data, table, check_crc=True):
    """bytes -> dict(sessions, nextregs, tests {id: record}, groups, lines). Raises Refused."""
    lines = checked_lines(data, check_crc) + ['END']
    res = {'sessions': [], 'nextregs': {}, 'tests': {}, 'groups': {}, 'subtests': {}, 'comments': [],
           'passes': [], 'history': {}, 'truncated': None}
    cur = None
    pas = None
    gorder = {g['id']: i for i, g in enumerate(table['groups'])}

    def new_pass(how, n, mode=None):
        p = {'index': len(res['passes']) + 1, 'from_line': n, 'how': how, 'mode': mode, 'groups': []}
        res['passes'].append(p)
        return p
    for n, ln in enumerate(lines[1:-1], 2):
        if not ln:
            raise Refused('line %d: empty' % n)
        if ln.startswith('#'):
            res['comments'].append(ln)
            continue
        rec, _, rest = ln.partition(' ')
        f = kv(rest.split(), n)
        if rec == 'H':
            if 'suite' in f:
                cur = {'header': {}}
                res['sessions'].append(cur)
                pas = new_pass('session', n, f.get('mode'))
            if cur is None:
                raise Refused('line %d: H line before the first "H suite=" line' % n)
            cur['header'].update({k: v for k, v in f.items() if v is not True})
        elif rec == 'X':
            res['truncated'] = f.get('lost', '?')
        elif rec == 'C':
            raise Refused('line %d: a continuation record: give the intake NXSUITE.TXT with its parts beside it'
                          % n)
        elif rec == 'R':
            if 'nr' not in f or 'v' not in f:
                raise Refused('line %d: R line without nr= / v=' % n)
            res['nextregs'][f['nr'].upper()] = f['v'].upper()
        elif rec == 'P':
            if 'pass' not in f:
                raise Refused('line %d: P line without pass=' % n)
            if pas is not None and not pas['groups'] and pas['how'] == 'session':
                pas['how'], pas['mode'] = 'marker', f.get('mode', pas['mode'])     # the session's first pass
            else:
                pas = new_pass('marker', n, f.get('mode'))
        elif rec == 'G':
            if 'id' not in f:
                raise Refused('line %d: G line without id=' % n)
            if 'end' not in f:
                if pas is None:
                    pas = new_pass('implied', n)
                elif pas['groups'] and gorder.get(f['id'], 99) <= gorder.get(pas['groups'][-1], 99):
                    # groups run in table order within a pass: one that does not follow starts a new pass
                    pas = new_pass('implied', n, 'from %s' % f['id'])
                pas['groups'].append(f['id'])
            g = res['groups'].setdefault(f['id'], {})
            if 'end' in f:
                g['fails'] = int(f.get('fails', '0'))
                g['ended'] = True
            else:
                g['started'] = True
        elif rec == 'T':
            tid, st = f.get('id'), f.get('st')
            if not tid or not st:
                raise Refused('line %d: T line without id= / st=' % n)
            if st not in STATUSES:
                raise Refused('line %d: unknown status %r' % (n, st))
            parent = None
            if tid not in table['by_test']:
                parent = next((p for pre, p in table['prefixes'].items() if tid.startswith(pre)), None)
                if parent is None:
                    raise Refused('line %d: unknown test id %r' % (n, tid))
            r = {'id': tid, 'status': st, 'line': n, 'pass': pas['index'] if pas else 0}
            for k in ('v', 'u', 'n', 'min', 'max', 'why', 'exp', 'c'):
                if k in f:
                    r[k] = f[k]
            r['extra'] = {k: v for k, v in f.items() if k not in r and k not in ('id', 'st') and v is not True}
            res['history'].setdefault(tid, []).append(r)
            if parent:
                res['subtests'].setdefault(parent, {})[tid] = r
            else:
                res['tests'][tid] = r          # the latest pass wins (disagreements: passes_disagree)
        else:
            raise Refused('line %d: unknown record %r' % (n, rec))
    if not res['sessions']:
        raise Refused('no "H suite=" header')
    pick_records(res)
    return res


FINAL = ('PASS', 'FAIL', 'INFO', 'OPERATOR', 'HANG-GUARD')


def invalid_why(r, res):
    """a final-looking record that a fact from the same pass shows to be no answer -> reason, else None"""
    if r['id'] == 'XH1' and r['status'] == 'FAIL':
        # the DMA was already deaf in that pass (XH2 of the same pass could not copy one byte before its
        # own lock): auto-restart was never started, so the FAIL says nothing about it
        x2 = [q for q in res['history'].get('XH2', []) if q['pass'] == r['pass']]
        if x2 and x2[0].get('extra', {}).get('before') == '$00':
            return 'the DMA was deaf in that pass (XH2 before=$00: no reset since an earlier XH2 lock)'
    if r['id'] == 'XH2' and r['status'] in ('PASS', 'FAIL') and r.get('extra', {}).get('before') == '$00':
        # builds up to e8cc11b sent the lock again to a DMA that was already deaf: "deaf" then says nothing
        return 'the DMA was already deaf before the WR4 byte (before=$00: still locked from an earlier XH2)'
    return None


def pick_records(res):
    """per test the record the verdict uses: the latest pass with a final status (PASS / FAIL / INFO /
    OPERATOR / HANG-GUARD) that no fact of its own pass makes void; a later SKIP / PENDING-OPERATOR /
    not-selected line never replaces it. With no final record: the latest line."""
    res['voided'] = []
    for tid, hist in res['history'].items():
        if tid not in res['tests']:
            continue
        best = None
        for r in hist:
            why = invalid_why(r, res)
            if why:
                res['voided'].append((tid, r['pass'], why))
                continue
            if r['status'] in FINAL:
                best = r
        res['tests'][tid] = best or hist[-1]
    # XH2: the lock pass (v deaf / copied) and its follow-ups after a reset (v reset-frees / still-locked)
    # are two answers, both kept: the verdict uses the lock pass, the note states every follow-up
    hist = res['history'].get('XH2', [])
    if 'XH2' in res['tests'] and hist:
        voided = {pas for t, pas, _ in res['voided'] if t == 'XH2'}
        ok = [r for r in hist if r['status'] in FINAL and r['pass'] not in voided]
        lock = [r for r in ok if r.get('v') in ('deaf', 'copied')]
        follow = [r for r in ok if r.get('v') in ('reset-frees', 'still-locked')]
        base = lock[-1] if lock else (follow[-1] if follow else res['tests']['XH2'])
        res['tests']['XH2'] = dict(base, follow=follow)


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def sub_records(res, cid):
    """the sub-case records that decide claim cid (SUBCLAIMS); a FAIL that differs from the model only in the
    ignored F bits is made a PASS with a note -> (records, notes); None if cid is not a sub-case claim"""
    if cid not in SUBCLAIMS:
        return None
    parent, pat, ign = SUBCLAIMS[cid]
    recs, notes = [], []
    for tid, r in sorted(res['subtests'].get(parent, {}).items()):
        if not re.match(pat, tid):
            continue
        f, fe = r['extra'].get('f'), r['extra'].get('fexp')
        if r['status'] == 'FAIL' and ign and r['extra'].get('code') == 'F' and f and fe and \
                (int(f.lstrip('$'), 16) ^ int(fe.lstrip('$'), 16)) & ~ign & 0xFF == 0:
            r = dict(r, status='PASS')
            notes.append('%s: F %s, model %s - differs only in bits the docs call unsure (mask $%02X); data right'
                         % (tid, f, fe, ign))
        recs.append(r)
    return recs, notes


FINAL = ('PASS', 'FAIL', 'INFO', 'OPERATOR', 'HANG-GUARD')


def passes_disagree(res, final_only=True):
    """tests run in more than one pass whose status, value or extras differ -> [(id, [(pass, summary)])]. Only
    final results are compared (final_only): a PENDING-OPERATOR or SKIP line in another pass of the same build
    (RUN ALL after the visual pass, an opt-in group not selected) is not a different answer (board run 11
    listed 29 tests for that reason alone)."""
    out = []

    def summ(r):
        return '%s v=%s %s' % (r['status'], r.get('v', '-'),
                               ' '.join('%s=%s' % kv_ for kv_ in sorted(r['extra'].items())))
    for tid, hist in sorted(res['history'].items()):
        if final_only:
            hist = [r for r in hist if r['status'] in FINAL]
            if tid == 'XH2':        # the lock pass and its follow-ups after resets are different steps (_xh2)
                hist = [r for r in hist if r.get('v') in ('deaf', 'copied')]
        if len({r['pass'] for r in hist}) < 2:
            continue
        if len({summ(r) for r in hist}) > 1:
            out.append((tid, [(r['pass'], summ(r)) for r in hist]))
    return out


def verdicts(res, table):
    """-> {claim: {verdict, value, spread, unit, choice, tests, why, notes}}"""
    out = {}
    for c in table['claims']:
        cid = c['id']
        tests = [x['id'] for x in table['tests'] if cid in x['claims']]
        recs = [res['tests'][t] for t in tests if t in res['tests']]
        sub = sub_records(res, cid)
        v = {'verdict': 'not-run', 'tests': tests, 'value': None, 'spread': None, 'unit': c['unit'], 'choice': None,
             'why': None, 'result_type': c['result_type'], 'notes': []}
        if sub and sub[0]:
            recs, v['notes'] = sub
            v['tests'] = sorted({r['id'] for r in recs})
        if not recs:
            v['why'] = 'not in the file'
            out[cid] = v
            continue
        src = (res['sessions'][0]['header'].get('src') or '')[:7]
        fixed = []
        for r in recs:
            why = KNOWN_FAULTS.get(r['id'], {}).get(src)
            if r.get('extra', {}).get('method') == 'fault':
                why = 'the program found its own timing out of range (method=fault)'
            if why and r['status'] in ('PASS', 'FAIL', 'INFO'):
                r = dict(r, status='SKIP', why='test-fault')
                v['notes'].append('%s: test fault in build %s, not a finding - %s' % (r['id'], src, why))
            if r['status'] in ('PASS', 'FAIL', 'INFO', 'OPERATOR') and (r['id'], cid) in DERIVE:
                got = DERIVE[(r['id'], cid)](r.get('extra', {}), r, src)
                if got:
                    if got[0]:
                        r = dict(r, status=got[0])
                    v['notes'].append('%s: %s' % (r['id'], got[1]))
            fixed.append(r)
        recs = fixed
        for r in recs:
            ans = [(q['pass'], q.get('v')) for q in res['history'].get(r['id'], []) if q['status'] == 'OPERATOR'
                   and r['id'] != 'XH2']                # XH2's follow-ups follow different resets: _xh2 states each
            if len({a for _, a in ans}) > 1:
                v['notes'].append('%s: the answers differ between passes (%s); the verdict uses the latest' % (
                    r['id'], ', '.join('pass %d %s' % a for a in ans)))
            for tid, pas, why in res.get('voided', []):
                if tid == r['id']:
                    v['notes'].append('%s: pass %d not used - %s' % (tid, pas, why))
        st = [r['status'] for r in recs]
        if 'HANG-GUARD' in st:
            v['verdict'], v['why'] = 'hung', 'the machine stopped in %s' % ','.join(
                r['id'] for r in recs if r['status'] == 'HANG-GUARD')
        elif all(r['status'] == 'SKIP' and r.get('why') == 'left-out' for r in recs):
            v['verdict'], v['why'] = 'left-out', ','.join(r['id'] for r in recs)
        elif all(s in ('SKIP', 'PENDING-OPERATOR', 'VISUAL-SHOWN', 'VISUAL') for s in st):
            v['verdict'] = 'pending-operator' if 'PENDING-OPERATOR' in st else 'not-run'
            v['why'] = ','.join('%s:%s' % (r['id'], r.get('why', r['status'].lower())) for r in recs)
        else:
            done = [r for r in recs if r['status'] in ('PASS', 'FAIL', 'INFO', 'OPERATOR')]
            # a table test (N01) that only lists numbers does not outvote a test made for the claim
            own = [r for r in done if not (r['id'] in TABLE_TESTS and r['status'] == 'INFO'
                                           and (r['id'], cid) not in CLAIM_KEYS)]
            if own and len(own) < len(done):
                v['notes'].append('also: the %s* table of %s' % (TABLE_TESTS[[r for r in done if r not in own][0]['id']],
                                                               [r for r in done if r not in own][0]['id']))
                done = own
            stt = []
            for r in done:
                key = CLAIM_KEYS.get((r['id'], cid))
                stt.append(r['extra'].get(key, r['status']) if key else r['status'])
            if 'FAIL' in stt:
                v['verdict'] = 'disproved'
            elif stt and all(s == 'PASS' for s in stt):
                v['verdict'] = 'confirmed'
            elif any(s == 'OPERATOR' for s in stt):
                v['verdict'] = 'operator'
                v['choice'] = ','.join('%s:%s' % (r['id'], r['extra'].get('means', r.get('v'))) for r in done)
            else:
                v['verdict'] = 'measured' if c['result_type'] == 'number' else 'choice' if c['result_type'] == 'choice' \
                    else 'measured'
            words = [x for x in stt if x not in STATUSES]
            if words and v['verdict'] not in ('disproved', 'confirmed'):
                v['verdict'], v['choice'] = 'choice', ','.join(words)
            r0 = done[0]
            val, lo, hi = num(r0.get('v')), num(r0.get('min')), num(r0.get('max'))
            if val is not None:
                v['value'] = val
                if lo is not None and hi is not None:
                    v['spread'] = round((hi - lo) / 2, 2)
            elif not v['choice']:
                v['choice'] = r0.get('v')
            v['unit'] = r0.get('u') if r0.get('u') not in (None, '-') else c['unit']
            if r0['id'] in TABLE_TESTS and cid not in {k[1] for k in CLAIM_KEYS if k[0] == r0['id']}:
                # a table test: its own v is a row count; the numbers are its sub-lines
                pre = TABLE_TESTS[r0['id']]
                v['value'], v['spread'], v['verdict'] = None, None, 'measured'
                v['choice'] = 'table'
                v['notes'].append('the numbers are the %d %s* lines (JSON "subtests" of %s)' % (
                    len(res['subtests'].get(r0['id'], {})), pre, r0['id']))
        out[cid] = v
    return out


# ---------------------------------------------------------------- results stated from a test's keys
# (test, claim) -> f(extra, record, src) -> (status or None, note): the rule the sources give, applied to
# the numbers on the line; the note says what the board showed in words. A status here replaces the
# test's own PASS / FAIL / INFO for that claim only.
def _k(e, key):
    return num(e.get(key))


def _within(x, want, tol):
    return x is not None and abs(x - want) <= tol


# builds whose D02 key '3' was the timing byte %11 (4 clocks a cycle, book ch 5: 00 4, 01 3, 10 2, 11 4)
D02_OLD = ('32af2e0', '562b0db', 'd99fbf8', '8906baa', 'a937cdd', 'dc8521e', '7bf9a73', 'd2a3863', 'a39e286',
           '8d8f182', '57d7b56')


def _d02_rows(e, src):
    """D02 -> {kind + t: (T at 3.5 MHz, clocks at 28 MHz)}; t = a (no timing byte), 3 (%01), 4 (%11), 2 (%10).
    The 3.5 MHz values on the line are 28 MHz clocks: / 8 = T."""
    rows = {}
    for kind in 'mp':
        for t in 'a234':
            a35, a28 = _k(e, '%s%s35' % (kind, t)), _k(e, '%s%s28' % (kind, t))
            rows[kind + t] = (None if a35 is None else round(a35 / 8, 2), a28)
        if src in D02_OLD:
            rows[kind + '4'], rows[kind + '3'] = rows[kind + '3'], (None, None)
    return rows


def _d02_words(r):
    parts = []
    for t, name in (('a', 'no timing byte'), ('3', 'byte %01 (3)'), ('4', 'byte %11 (4)'), ('2', 'byte %10 (2)')):
        m = r['m' + t]
        if m[0] is not None or m[1] is not None:
            parts.append('%s %s T at 3.5 MHz / %s clocks at 28 MHz' % (name, m[0], m[1]))
    return '; '.join(parts) + ' (memory to memory; to port $5B with no byte: %s / %s)' % r['pa']


def _d02_default(e, rec, src):
    r = _d02_rows(e, src)
    a35, a28 = r['ma']
    ok = _within(a35, 6, 0.1) and _within(a28, 6, 0.1)
    if r['m3'][0] is not None:          # new builds: also equal to the explicit 3-cycle byte
        ok = ok and _within(r['m3'][0], a35, 0.1) and _within(r['m3'][1], a28, 0.1)
    note = 'board: %s. No timing byte = %s.' % (
        _d02_words(r), 'two 3-clock cycles (6 a byte): the default is 3, not the Z80 standard 4' if ok
        else 'not two 3-clock cycles')
    if src in D02_OLD:
        note += (" (The line printed FAIL because this build compared it with the byte %11, which the book's "
                 "table makes 4 clocks; that comparison was the test's fault, not the DMA's.)")
    return ('PASS' if ok else 'FAIL'), note


def _d02_cost(e, rec, src):
    r = _d02_rows(e, src)
    bad = []
    for t, want in (('a', 6), ('2', 4)):
        for i, spd in ((0, '3.5 MHz'), (1, '28 MHz')):
            for kind in 'mp':
                x = r[kind + t][i]
                if x is not None and not _within(x, want, 0.1):
                    bad.append('%s, %s, %s: %s, not %s' % ('memory' if kind == 'm' else 'port',
                               'no byte' if t == 'a' else 'cycle length 2', spd, x, want))
    note = 'board: %s.' % _d02_words(r)
    note += (' Holds: 6 with no timing byte and 4 with cycle length 2, at both speeds.' if not bad else
             ' Differs: %s.' % '; '.join(sorted(set(bad))))
    return ('PASS' if not bad else 'FAIL'), note


def _d04(e, rec, src):
    out35, out28 = [], []
    for p in (12, 55, 100, 144):
        a, b = _k(e, 'p%d_35' % p), _k(e, 'p%d_28' % p)
        if a is not None:
            out35.append('P=%d %.1f T (4P+3 = %d, %+.1f %%)' % (p, a / 8, 4 * p + 3, (a / 8 / (4 * p + 3) - 1) * 100))
        if b is not None:
            out28.append('P=%d %.1f (32P = %d: %+.1f %%; 32P+3: %+.1f %%)' % (
                p, b, 32 * p, (b / (32 * p) - 1) * 100, (b / (32 * p + 3) - 1) * 100))
    p0, p1 = _k(e, 'p0_35'), _k(e, 'p1_35')
    one = '' if p0 is None or p1 is None else (
        ' P=1 at 3.5 MHz: %.1f T against %.1f T with P=0, so P=1 %s.' % (
            p1 / 8, p0 / 8, 'has no effect' if abs(p1 - p0) <= 0.05 * p0 else
            'does slow the transfer (the claim says it has no effect)'))
    return None, 'board, clocks per byte at 28 MHz: %s; at 3.5 MHz: %s.%s' % (
        '; '.join(out28), '; '.join(out35), one)


def _d05(e, rec, src):
    v, c = num(rec.get('v')), _k(e, 'cont')
    ok = v is not None and v >= 95 and c == 0
    return ('PASS' if ok else 'FAIL'), (
        'board: during a P = 100 burst transfer the CPU loop ran at %s %% of its speed without DMA (claim: more '
        'than 95 %%); during a continuous transfer it made %s passes (0 = frozen for the whole block).' % (
            rec.get('v'), e.get('cont')))


def _d13(e, rec, src):
    op, tr, fi, fx = (_k(e, x) for x in ('op', 'tr', 'fi', 'fx'))
    if None in (op, tr, fi, fx) or not fx:
        return None
    return None, ('board at 28 MHz, clocks per byte: opaque %s, transparent (half the bytes skipped) %s - the '
                  'skipped bytes still cost their write cycle; fill %s against a fixed-source copy %s = %.2f x '
                  '(no read cycle).' % (op, tr, fi, fx, fi / fx))


def _sp10(e, rec, src):
    got = [num(rec.get('v'))] + [_k(e, k) for k in ('s2', 's4', 's8')]
    mv = _k(e, 'moved')
    # 1,824 clocks a line; a drawn sprite 1 + 16 x scale, each of the other 128 (hidden or off the line) 1:
    # the first k with k x 16s + 128 >= 1824 is dropped
    want = [-(-1696 // (16 * s)) for s in (1, 2, 4, 8)]
    ok = got == want and (mv is None or mv == 128 - (want[0] - 1))
    fit = ['%d x %d + %d = %d' % (k - 1, 1 + 16 * s, 129 - k, (k - 1) * (1 + 16 * s) + 129 - k)
           for k, s in zip(want, (1, 2, 4, 8))]
    return ('PASS' if ok else 'FAIL'), (
        'board: the overflow flag sets at k = %s for scale 1 / 2 / 4 / 8 (sprites moved off the line before it '
        'clears: %s). The model "1,824 clocks a line; a drawn sprite costs 1 + 16 x scale, every other of the 128 '
        '(hidden ones too) 1; the sprite that brings the total to 1,824 is dropped" predicts %s; the largest '
        'sets that fit cost %s clocks. %s' % (
            ' / '.join(str(int(x)) if x is not None else '?' for x in got), e.get('moved'),
            ' / '.join(map(str, want)), ', '.join(fit), 'The board agrees.' if ok else 'The board does not agree.'))


def _f06_60(e, rec, src):
    l60, i60, l50, i50 = (_k(e, x) for x in ('l60', 'i60', 'l50', 'i50'))
    if None in (l60, i60) or not i60:
        return None
    gap = int(l60 - i60)
    return ('PASS' if gap == 40 else 'FAIL'), (
        'board: at 60 Hz the ULA interrupt comes at line %d of %d, %d lines before the display starts (line 0); '
        'at 50 Hz at line %s of %s, %s lines before.' % (
            i60, l60, gap, e.get('i50'), e.get('l50'), '?' if None in (l50, i50) else int(l50 - i50)))


def _v19(e, rec, src):
    fr, se, te = _k(e, 'frames'), _k(e, 'secs'), _k(e, 'tenths')
    if not fr or not se:
        return None
    if te is None:      # whole seconds off the watch: the true time is in [s, s + 1), plus reaction
        secs = se
        lo, hi = fr / (se + 1.2), fr / (se - 0.2)
        how = 'whole seconds: the true time was %d-%d s (the watch shows whole seconds) +-0.2 s reaction' % (
            se, se + 1)
    else:
        secs = se + te / 10
        lo, hi = fr / (secs + 0.3), fr / (secs - 0.3)
        how = 'tenths typed: +-0.3 s (reading and reaction)'
    say = 'board: %d frames in %s s = %s Hz (cable %s); %s, so %.2f-%.2f Hz. %s' % (
        fr, secs, rec.get('v'), e.get('cable', '?'), how, lo, hi,
        '50.00 Hz lies inside that range.' if lo <= 50 <= hi else
        '50.00 Hz lies outside that range: time it again with tenths to be sure.')
    w, c0, c1 = _k(e, 'ctcw'), _hex(e.get('c0')), _hex(e.get('c1'))
    if None not in (w, c0, c1):
        ticks = 256 * w + c0 - c1          # CTC channel 3, prescaler 256: one tick = 256 clocks of 28 MHz
        cs = ticks * 256 / 28e6
        if cs > 0:
            say += (' Same interval by the CTC (28 MHz clock / 256, book ch 6): %d ticks = %.2f s, so %.3f Hz; '
                    'the watch said %s s (%+.2f s). %s' % (
                        ticks, cs, fr / cs, secs, secs - cs,
                        "The watch and the machine agree: the rate by the watch is the machine's."
                        if abs(secs - cs) <= 0.3 else
                        'The watch time differs from the CTC time by more than the reading error: a timing error '
                        'at the watch (start / stop) - or the 28 MHz clock itself is off by %.2f %%, which only the '
                        'watch can show.' % (100 * (secs - cs) / cs)))
    return None, say


def _hex(v):
    try:
        return int(v[1:], 16) if v and v.startswith('$') else None
    except ValueError:
        return None


def _xt2(e, rec, src):
    f1, f2, f3, j1, e0, e1 = (num(rec.get('v')),) + tuple(_k(e, k) for k in ('f2', 'f3', 'j1', 'exp0', 'exp1'))
    if None in (f1, f2, e0, e1):
        return None
    if f1 == e0 and f2 == e1:
        how = 'the frame being drawn kept the old length and the next one had the new: held to the frame end'
    elif f1 == e1:
        how = ('the frame being drawn ran on to the NEW length at once (not held to the frame end)%s' % (
            '' if f2 == e1 else ', then a %d-line frame, then %d' % (f2, f3 or 0)))
    else:
        how = 'neither the old nor the new length (f1 %s, f2 %s, f3 %s)' % (f1, f2, f3)
    return None, 'board: $03 written at line 100 of a %d-line frame (old %d, new %d lines): that frame was %d lines; %s.' % (
        e0, e0, e1, f1, how)


def _xt4(e, rec, src):
    d8 = e.get('nrd8') or ''
    if e.get('p3ffd') == 'skipped' or (d8.startswith('$') and int(d8[1:], 16) & 1):
        return None, ('board: $7FFD paged MMU 6 / 7 = %s / %s; the $3FFD half was SKIPPED (NextReg $D8 bit 0 set at '
                      'launch: the +3 disk ports are trapped), so b6 / b7 = $FF are not an answer.' % (e.get('a6'), e.get('a7')))
    return None


def _v10(e, rec, src):
    w = rec.get('v')
    say = {'split-clean': 'the picture split at about line 96 with a clean edge: $12 took effect mid-frame',
           'split-jitter': ('the picture split at about line 96, the edge stepping part-way along a line or '
                            'jittering: $12 took effect mid-frame, at the point in the line where the CPU wrote it'),
           'no-split': 'no split at line 96: $12 did not take effect mid-frame (or the picture was something else)',
           'split-96': 'the picture split at line 96 (older build: clean or jittering not asked)',
           'frame-start': 'red two thirds: $12 taken at the frame start',
           'other': 'something else (older build; see the operator\'s words)'}.get(w)
    if not say:
        return None
    st = 'PASS' if w in ('split-clean', 'split-jitter', 'split-96') else ('FAIL' if w in ('no-split', 'frame-start')
                                                                         else None)
    return st, 'operator: %s.' % say


def _v18(e, rec, src):
    a, b = e.get('o33'), e.get('o32')
    if not a or not b:
        return None
    lit = [o for o, w in (('33', a), ('32', b)) if w == 'two']
    if a == 'two' and b == 'one':
        st, how = 'PASS', 'copper line 0 is Layer 2 row 0 with $64 = 33, not with 32'
    elif a == 'one' and b == 'two':
        st, how = 'FAIL', 'copper line 0 is Layer 2 row 0 with $64 = 32, not with 33'
    else:
        st, how = None, 'not one setting alone (row 0 lit with: %s)' % (', '.join(lit) or 'neither')
    part = [o for o, w in (('33', a), ('32', b)) if w.startswith('part-')]
    if part:
        how += ('; a part-lit row 0 (with $64 = %s) means the colour change came part-way along that row: the '
                'copper line starts (part-right) or ends (part-left) inside the Layer 2 row, not at its left edge'
                % ' and '.join(part))
    return st, 'operator: $64 = 33 -> %s, $64 = 32 -> %s (two = row 0 lit by the copper at its line 0 plus ' \
        'the reference; part-left / part-right = row 0 white on that part only): %s.' % (a, b, how)


def _v05(e, rec, src):
    say = {'lower': ('PASS', 'Layer 2 showed through the side borders of lines 96-191, where its colour was made equal to '
                             '$14: a border in the $14 colour is transparent'),
           'lower-green': ('PASS', 'Layer 2 showed through the side borders of lines 96-191 (a border in the $14 colour '
                                   'is transparent), then a strip in the fallback colour ($4A, green for the test) '
                                   'out to the screen edge: the screen shows border beyond the 320 x 256 Layer 2 '
                                   '(book N14 says nothing is drawn beyond the wide area)'),
           'lower-black': ('PASS', 'Layer 2 showed through the side borders of lines 96-191 (a border in the $14 colour '
                                   'is transparent), then black, not the green fallback, out to the screen edge: '
                                   'the picture ends with the 320 x 256 wide area there (book N14)'),
           'none': ('FAIL', 'no Layer 2 in the side borders of lines 96-191 (plain or black there): the layer below '
                            'did not show through a border in the $14 colour'),
           'other': (None, 'something else - see the operator\'s notes')}.get(rec.get('v'))
    return (say[0], 'operator: %s.' % say[1]) if say else None


def _v07(e, rec, src):
    a, b = e.get('c0'), e.get('c1')
    if not a or not b:
        return None
    st = 'PASS' if (a, b) == ('top', 'both') else ('FAIL' if a == 'both' or b == 'top' else None)
    return st, ('operator: clip 0-255 / 0-191 -> %s band(s), clip 0-159 / 0-255 -> %s (both = the bottom 32 rows of '
                'the 320 x 256 Layer 2 shown too). The claim: top, then both.' % (a, b))


def _v08(e, rec, src):
    a, b = e.get('s0'), e.get('s1')
    if not a or not b:
        return None
    if a == 'none' and b == 'none':
        st = 'PASS'
    elif a == 'none' and b in ('left', 'right'):
        st = 'FAIL'
    else:
        st = None
    how = ('operator: 640 x 256 Layer 2 blocks over red / blue tiles - no scroll: %s; Layer 2 and tilemap both '
           'scrolled one step: %s (none = no red at any block edge; left / right = a one-dot red line on that '
           'edge). ' % (a, b))
    if st == 'PASS':
        how += 'The layers line up and a 640 scroll step moved Layer 2 by 2 dots, like the tilemap: the claim.'
    elif st == 'FAIL':
        how += 'A red line only after the scroll: a 640 scroll step moved Layer 2 by 1 dot, not 2.'
    elif a != 'none':
        how += 'Without a scroll the layers did not line up, so the scroll step is not decided by this run.'
    return st, how


def _vone(table):
    """a one-question V test: v = word -> (status, what the operator saw)"""
    def f(e, rec, src):
        say = table.get(rec.get('v'))
        return (say[0], 'operator: %s.' % say[1]) if say else None
    return f


def _vtwo(k1, t1, k2, t2):
    """a two-question V test (keys k1 / k2): PASS when both answers are the claim's, FAIL when either is the
    named other one, else no status"""
    def f(e, rec, src):
        a, b = t1.get(e.get(k1)), t2.get(e.get(k2))
        if not a or not b:
            return None
        st = 'PASS' if a[0] == 'PASS' and b[0] == 'PASS' else ('FAIL' if 'FAIL' in (a[0], b[0]) else None)
        return st, 'operator: %s; %s.' % (a[1], b[1])
    return f


OTHER = (None, "something else - see the operator's notes")
_v17 = _vone({'lower': ('PASS', 'the upper row stayed inside the clip window, the lower row (below the copper MOVE of $15 '
                                'with its own value) ran past it: the MOVE reset the clip windows'),
              'inside': ('FAIL', 'both rows stayed inside the clip window: the copper MOVE to $15 did not reset it'),
              'other': OTHER})
_v01u = {'book': ('PASS', 'sprite clip window: display dots without the border, ignored over the border without $15 bit 5, '
                          '2-dot units across the wide area with it'),
         'one-dot': ('FAIL', 'sprite clip window over the border with $15 bit 5 still in display dots (not 2-dot units)'),
         'other': OTHER}
_v01l = {'late': ('PASS', 'a copper sprite change shown one line after the line it was made on'),
         'same-line': ('FAIL', 'a copper sprite change shown on the line it was made on'),
         'two-late': ('FAIL', 'a copper sprite change (WAIT line 157) shown TWO lines after the line it was made on '
                              '(row 159); TECHNIQUES.md:331 already says to write at WAIT(line N-2) for line N'),
         'other': OTHER}
_v03 = _vtwo('s', {'wide': ('PASS', 'X scale 4 after rotation: the bar stayed wide'),
                   'tall': ('FAIL', 'X scale 4 with rotation gave a tall bar: scale before rotation'), 'other': OTHER},
             'o', {'tl': ('PASS', 'rotate + X mirror left the red corner top left: rotation first, then the mirror'),
                   'br': ('FAIL', 'rotate + X mirror put the red corner bottom right: the mirror first'), 'other': OTHER})
_v06 = _vone({'claim': ('PASS', 'the priority colour drew over the sprites (in order SLU and in blend mode 110), and not '
                                'where its colour was the transparent one'),
              'no-prio': ('FAIL', 'the sprites drew over every block: the priority bit did not lift Layer 2'),
              'other': OTHER})
_v09 = _vtwo('a', {'on': ('PASS', '256 x 192 scrolled X 128 / Y 96: the stripes met on the square (wrap at 256 / 192)'),
                   'off': ('FAIL', '256 x 192: the stripes missed the square (not wrapping at 256 / 192)'), 'other': OTHER},
             'w', {'on': ('PASS', '320 x 256 scrolled X 160 / Y 128: the stripes met on the square (wrap at 320 / 256)'),
                   'off': ('FAIL', '320 x 256: the stripes missed the square (not wrapping at 320 / 256)'), 'other': OTHER})
_v11 = _vone({'wrap': ('PASS', "the tiles past bank 7 offset $1FFF took page 14's start (green): the offset wraps at 8K"),
              'page15': ('FAIL', 'the tiles past bank 7 offset $1FFF came from page 15 (red)'), 'other': OTHER})
_v12 = _vtwo('t', {'grey': ('PASS', 'text mode: the background index (colour = $14) was transparent'),
                   'pink': ('FAIL', 'text mode: the background index with the $14 colour was drawn'), 'other': OTHER},
             'f', {'lower': ('PASS', '$6B bit 0 set by the copper at line 152 put the tiles marked "ULA over" over the ULA '
                                     'below that line only'),
                   'none': ('FAIL', '$6B bit 0 did not bring the tiles marked "ULA over" in front of the ULA'),
                   'other': OTHER})
_v13 = _vone({'claim': ('PASS', 'order %110 with $68 bits 6:5 = %01: tiles with attribute bit 0 = 0 in front of the '
                                'sprites, with bit 0 = 1 behind them'),
              'red-top': ('FAIL', 'the sprites drew over both tile blocks'), 'other': OTHER})
_v14 = _vone({'match': ('PASS', 'blend 110 (add, clamp 7), blend 111 (add, take 5) and stencil (ULA AND tilemap) each '
                                'matched the colour computed beside it'),
              'differ': ('FAIL', 'at least one of blend 110, 111 and stencil differed from the computed colour'),
              'other': OTHER})
_v04 = _vone({'claim': ('PASS', 'ULA and Layer 2 transparent by colour = $14, tilemap and sprites by index = $4C / $4B '
                                '(before the palette offset / palette)'),
              'differ': ('FAIL', 'one or more of the four bands did not follow its transparency rule'), 'other': OTHER})


def _v01u_f(e, rec, src):
    say = _v01u.get(e.get('u'))
    return (say[0], 'operator: %s.' % say[1]) if say else None


def _v01l_f(e, rec, src):
    say = _v01l.get(e.get('l'))
    return (say[0], 'operator: %s.' % say[1]) if say else None


RESETS = {'soft': 'an F4 soft reset', 'hard': 'a hard reset', 'power': 'power off and on'}


def _xh2(e, rec, src):
    fol = rec.get('follow') or []
    parts = []
    if rec.get('v') in ('deaf', 'copied'):
        parts.append('lock pass: one DMA byte copied before the WR4 byte $91, %s after it' % (
            'none' if rec['v'] == 'deaf' else 'still one'))
    for f in fol:
        how = RESETS.get(f.get('extra', {}).get('reset'), 'a reset the line does not name (build before the '
                                                       'reset question)')
        parts.append('after %s: %s' % (how, 'the DMA answered again' if f['v'] == 'reset-frees' else
                                       'still locked (no byte copied at the next start)'))
    if not fol:
        parts.append('no follow-up yet: power off and on (or a hard reset), start again, press H')
    st = None
    if rec.get('v') == 'deaf':
        st = 'PASS'
    elif rec.get('v') == 'copied':
        st = 'FAIL'
    return st, 'board: %s.' % '; '.join(parts)


DERIVE = {('V17', 'copper-15-resets-clip'): _v17, ('V01', 'spr-clip-units'): _v01u_f,
          ('V01', 'spr-change-one-line-late'): _v01l_f, ('V03', 'spr-scale-rotate'): _v03,
          ('V06', 'lay-l2-priority-bit'): _v06, ('V09', 'lay-l2-scroll-ranges'): _v09,
          ('V11', 'lay-tilemap-bank7-wrap'): _v11, ('V12', 'lay-tilemap-text-and-6b'): _v12,
          ('V13', 'lay-sprites-between-ula-tilemap'): _v13, ('V14', 'lay-blend-stencil'): _v14,
          ('V04', 'lay-transparency-rules'): _v04,
          ('XH2', 'dma-wr4-interrupt-lock'): _xh2, ('V07', 'lay-l2-wide-clip-default'): _v07, ('V08', 'lay-l2-640-whole-pixels'): _v08, ('V05', 'lay-border-transparent'): _v05, ('V18', 'frame-64-33-l2-top'): _v18, ('V10', 'lay-l2-flip-not-synced'): _v10,
          ('XT2', 'frame-timing-change-frame-end'): _xt2,
          ('XT4', 'mem-48k-timing-7ffd'): _xt4, ('D02', 'dma-default-cycle-length'): _d02_default, ('D02', 'dma-cost-per-byte'): _d02_cost,
          ('D04', 'dma-prescaler-rate'): _d04, ('D05', 'dma-burst-cpu-share'): _d05,
          ('D13', 'dma-blitter-transparent-fill'): _d13, ('SP10', 'spr-line-limit'): _sp10,
          ('F06', 'frame-60hz-display-start'): _f06_60, ('V19', 'sys-video-timing-frame-rate'): _v19}


# test faults found after a build went to a board: that build's PASS / FAIL of the test is not evidence
_G6T = ('continuous-mode transfers freeze the CPU and the CTC3 wraps were lost (fixed in g6_run after '
        'd99fbf8: the time is rebuilt from the raster line, CTC0 and CTC3)')
KNOWN_FAULTS = {'D02': {b: _G6T for b in ('32af2e0', '562b0db', 'd99fbf8')},
                'D04': {b: 'the tick count was overwritten before use (every P read 16)'
                        for b in ('32af2e0', '562b0db', 'd99fbf8')},
                'D05': {b: 'loop counts over different lengths were compared' for b in ('32af2e0', '562b0db', 'd99fbf8')}}
TABLE_TESTS = {'N01': 'nb.'}       # tests whose answer is a table of sub-lines, not one value


ISSUES = {'00': 'issue2', '01': 'issue3', '02': 'issue4'}     # NextReg $0F board id on a Next ($00 = $0A)


def board_name(res, board=None, table=None):
    """the platform part of a board record's name: --board, else the operator's machine answer (the "record"
    of that code in nxsuite_claims.json platforms), else from NextReg $00 / $0F: $0A with $0F = 0 / 1 / 2 ->
    issue2- / issue3- / issue4-compatible. The registers never name a maker or a Kickstarter: a clone of a
    board reads the same (an N-Go reads $0A / $00 like an official Issue 2). Anything else ->
    machine-xx-board-yy."""
    h = res['sessions'][0]['header']
    if board:
        return board
    op = operator(h, table)
    if op and op.get('model'):
        rec = {p_['code']: p_.get('record') for p_ in (table or load_table()).get('platforms', {}).get('list', [])}
        if rec.get(op['model']):
            return rec[op['model']]
    m = h.get('machine', 'nr00:$00').split(':')[-1].lstrip('$').lower()
    b = h.get('board', 'nr0f:$00').split(':')[-1].lstrip('$').lower()
    if m == '0a' and b in ISSUES:
        return ISSUES[b] + '-compatible'
    return 'machine-%s-board-%s' % (m, b)


def named_from(res, board=None, table=None):
    """what a board record's name came from: option / operator / registers"""
    if board:
        return 'option'
    op = operator(res['sessions'][0]['header'], table)
    rec = {p_['code']: p_.get('record') for p_ in (table or load_table()).get('platforms', {}).get('list', [])}
    return 'operator' if op and rec.get(op.get('model')) else 'registers'


def slug(x):
    return re.sub(r'[^a-z0-9.]+', '-', x.lower()).strip('-')


def is_board(platform):
    return platform is None or platform.lower() == 'board'


def write_json(res, table, path_in, data, board=None, outdir=OUTDIR, dry=False, platform=None):
    h = res['sessions'][0]['header']
    core = h.get('core', 'unknown')
    for s in res['sessions'][1:]:
        if s['header'].get('core') not in (None, core):
            raise Refused('the file mixes cores %s and %s: run the intake per core' % (core, s['header']['core']))
    op = operator(h, table)
    if is_board(platform):
        lab = '-' + slug(op['label']) if op and op.get('label') else ''      # no label: the old name
        path = os.path.join(outdir, '%s-%s%s.json' % (board_name(res, board, table), core, lab))
    else:
        path = os.path.join(outdir, 'emulator', '%s-%s.json' % (slug(platform), core))
    old = json.load(open(path)) if os.path.exists(path) else {}
    sha = hashlib.sha256(data).hexdigest()
    hist = old.get('intakes', [])
    hist.append({'date': datetime.date.today().isoformat(), 'file_sha256': sha})
    v = verdicts(res, table)
    doc = {'schema': 2,
           'platform': {'kind': 'board' if is_board(platform) else 'emulator',
                        'name': ((op or {}).get('model_name') or 'board') if is_board(platform) else platform,
                        'hardware_evidence': is_board(platform)},
           'board': {'name': board_name(res, board, table) if is_board(platform) else slug(platform),
                     'named_from': named_from(res, board, table) if is_board(platform) else 'platform',
                     'nr00': h.get('machine', ''), 'nr0f': h.get('board', ''),
                     'ram': h.get('ram'), 'video': h.get('video'), 'geom': h.get('geom')},
           'core': core, 'operator': op, 'intake_runs': len(hist), 'intakes': hist,
           'run': {'suite': h.get('suite'), 'src': h.get('src'), 'file': os.path.basename(path_in),
                   'file_sha256': sha, 'sessions': [s['header'] for s in res['sessions']],
                   'nextregs': res['nextregs'], 'tests': res['tests'], 'subtests': res['subtests'],
                   'comments': res['comments'], 'passes': res['passes'],
                   'parts': res.get('parts', []), 'truncated': res['truncated'],
                   'cable': next((r['extra']['cable'] for r in res['tests'].values() if 'cable' in r['extra']),
                                 None),
                   'passes_disagree': [{'id': t, 'records': [{'pass': p_, 'result': x} for p_, x in rs]}
                                       for t, rs in passes_disagree(res)]},
           'claims': v}
    if not dry:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', newline='\n') as fh:
            json.dump(doc, fh, indent=1, sort_keys=False)
            fh.write('\n')
    return path, doc


def report(doc, table, out=sys.stdout):
    v = doc['claims']
    order = {'disproved': 0, 'hung': 1, 'confirmed': 2, 'measured': 3, 'choice': 4, 'operator': 5,
             'pending-operator': 6, 'not-run': 7, 'left-out': 8}
    pf = doc.get('platform', {'kind': 'board', 'name': 'board'})
    if pf['kind'] == 'board':
        print('board %s  core %s  (intake run %d)' % (doc['board']['name'], doc['core'], doc['intake_runs']),
              file=out)
    else:
        print('EMULATOR %s  core %s  (intake run %d)  - emulator results, not hardware evidence' % (
            pf['name'], doc['core'], doc['intake_runs']), file=out)
    if len(doc['run'].get('parts', [])) > 1:
        print('files joined: %s' % ' + '.join(doc['run']['parts']), file=out)
    if doc['run'].get('truncated'):
        print('WARNING: TRUNCATED - the program could not store %s bytes; tests after the loss are missing'
              % doc['run']['truncated'], file=out)
    ps = doc['run'].get('passes', [])
    if len(ps) > 1:
        print('passes: %s (each test: its latest pass)' % '; '.join(
            '%d from line %d %s%s' % (p['index'], p['from_line'], p['how'], ' (%s)' % p['mode'] if p['mode'] else '')
            for p in ps), file=out)
    for cid in sorted(v, key=lambda c: (order.get(v[c]['verdict'], 9), c)):
        x, c = v[cid], table['by_claim'][cid]
        if x['verdict'] == 'confirmed':
            what = 'CONFIRMED'
        elif x['verdict'] == 'disproved':
            what = 'DISPROVED'
        elif x['verdict'] in ('measured', 'choice', 'operator'):
            if x['value'] is not None and not (x['verdict'] == 'choice' and x['choice']):
                what = 'MEASURED %s%s %s' % (x['value'], '' if x['spread'] is None else ' +-%s' % x['spread'],
                                           x['unit'] or '')
            else:
                what = '%s %s' % ('OPERATOR' if x['verdict'] == 'operator' else 'CHOICE', x['choice'])
        elif x['verdict'] == 'left-out':
            what = 'LEFT OUT (%s: reason below)' % x['why']
        else:
            what = 'NOT ANSWERED (%s: %s)' % (x['verdict'], x['why'])
        print('%-34s %s  [%s]' % (cid, what.strip(), ','.join(x['tests'])), file=out)
        if x['verdict'] in ('confirmed', 'disproved', 'measured', 'choice', 'operator'):
            vals = '; '.join('%s: %s' % (k, s) for k, s in c['values'].items())
            print('    expected  %s' % vals, file=out)
            print('    sources   %s' % ', '.join(c['sources']), file=out)
            for nt in x.get('notes', []):
                print('    note      %s' % nt, file=out)
            for t in x['tests']:
                f = table['by_test'][t].get('fields') if t in table.get('by_test', {}) else None
                if f:
                    print('    fields    %s: %s' % (t, f), file=out)
    n = {}
    for x in v.values():
        n[x['verdict']] = n.get(x['verdict'], 0) + 1
    print('summary: ' + ', '.join('%s %d' % kv_ for kv_ in sorted(n.items())), file=out)
    na = table.get('claims_not_tested', [])
    if na:
        b = doc['board']
        print('not answerable on this board configuration (frame measured: geom=%s video=%s cable=%s):' % (
            b.get('geom') or '?', b.get('video') or '?', doc['run'].get('cable') or 'not asked'), file=out)
        for x in na:
            print('  %-32s %s - %s' % (x['claim'], x['part'], x['status']), file=out)
        print('  reason: %s' % na[0]['reason'], file=out)
    rate_table(doc, out)
    lo = [t for t in table['tests'] if 'left_out' in t]
    if lo:
        print('left out on purpose (%d tests; the file says SKIP why=left-out):' % len(lo), file=out)
        for t in lo:
            print('  %-4s %s [%s]' % (t['id'], t['title'], ','.join(t['claims']) or '-'), file=out)
            print('       %s' % t['left_out'], file=out)
    lp = table.get('lessons_placed', [])
    if lp:
        print('platform / emulator lessons named nowhere else (%d): where each is answered, or why not:' % len(lp),
              file=out)
        for x in lp:
            print('  %-44s %s' % (x['lesson'], ('tests ' + x['placed']) if x['placed'] else 'left out'), file=out)
            print('       %s' % x['reason'], file=out)
    dis = doc['run'].get('passes_disagree', [])
    if dis:
        print('passes disagree (%d tests; the verdict used the latest pass with a final answer):' % len(dis), file=out)
        for d in dis:
            print('  %s' % d['id'], file=out)
            for r in d['records']:
                print('    pass %d: %s' % (r['pass'], r['result']), file=out)
    print('(nothing was changed in lessons or docs: apply the results in a reviewed change)', file=out)


def rate_table(doc, out=sys.stdout):
    """addition B: F06's numbers at 50 and 60 Hz side by side (F01 / F02 / I09 / F03 beside them)."""
    t = doc['run'].get('tests', {})
    f6 = t.get('F06')
    if not f6 or f6.get('status') not in ('INFO', 'PASS', 'FAIL'):
        return
    e = f6.get('extra', {})
    rows = [('lines per frame', 'l'), ('line length (T at 3.5 MHz)', 't'), ('ULA interrupt line ($C8 bit 0)', 'i')]
    print('50 / 60 Hz side by side (F06; the start rate first measured, the other after $05 bit 2):', file=out)
    print('  %-32s %10s %10s' % ('', '50 Hz', '60 Hz'), file=out)
    for name, k in rows:
        print('  %-32s %10s %10s' % (name, e.get(k + '50', '?'), e.get(k + '60', '?')), file=out)
    also = []
    for tid in ('F01', 'F02', 'I09', 'F03'):
        r = t.get(tid)
        if r and r.get('status') in ('PASS', 'FAIL', 'INFO'):
            also.append('%s v=%s' % (tid, r.get('v')))
    if also:
        print('  beside it: %s (F01 / F02 / I09 at the start rate, F03 at the other)' % ', '.join(also), file=out)


def compare(a, b, out=sys.stdout):
    A, B = json.load(open(a)), json.load(open(b))
    diff = 0
    for cid in sorted(set(A['claims']) | set(B['claims'])):
        x, y = A['claims'].get(cid, {}), B['claims'].get(cid, {})
        kx = (x.get('verdict'), x.get('value'), x.get('choice'))
        ky = (y.get('verdict'), y.get('value'), y.get('choice'))
        if kx != ky:
            diff += 1
            print('%-34s %s %s | %s %s' % (cid, kx[0], kx[1] if kx[1] is not None else kx[2] or '',
                                         ky[0], ky[1] if ky[1] is not None else ky[2] or ''), file=out)
    def who(D):
        pf = D.get('platform', {'kind': 'board', 'name': 'board'})
        return '%s %s' % ('board ' + D['board']['name'] if pf['kind'] == 'board' else 'emulator ' + pf['name'],
                          D['core'])
    print('%d claims differ between %s (%s) and %s (%s)' % (
        diff, os.path.basename(a), who(A), os.path.basename(b), who(B)), file=out)
    if A.get('platform', {}).get('kind', 'board') != B.get('platform', {}).get('kind', 'board'):
        print('board vs emulator: the emulator side is what that emulator does, not hardware evidence', file=out)
    return diff


# tests whose method has a known resolution wider than its within-run spread (value units)
RUN_TOL = {'I10': 12}
# extras that are memory contents, not measurements (S03: CRCs of page 96 and the suite's own slot-6 page,
# whatever the RAM held), left out of --runs
RUN_IGNORE = {'S03': ('crc0', 'crc96')}


def diff_records(tid, have):
    """two or more result records of one test -> [why] they differ beyond tolerance: the status, a word value, or
    a number (v or an extra) further apart than the larger within-run min-max, a method resolution (RUN_TOL),
    +-1 for counts, 0.5 % or 0.05 for fixed-point values. Used by --runs and --conformance."""
    why = []
    if len({x['status'] for x in have}) > 1:
        why.append('status ' + '/'.join(x['status'] for x in have))
    keys = ['v'] + sorted(set().union(*(set(x.get('extra') or {}) for x in have)))
    for k in keys:
        if k in RUN_IGNORE.get(tid, ()):
            continue
        get = (lambda x: x.get('v')) if k == 'v' else (lambda x, k=k: (x.get('extra') or {}).get(k))
        vals = [num(get(x)) for x in have]
        if any(v is None for v in vals):
            raw = {str(get(x)) for x in have}
            if len(raw) > 1:
                why.append('%s %s' % (k, '/'.join(str(get(x)) for x in have)))
            continue
        tol = RUN_TOL.get(tid, 0)
        raw = [str(get(x)) for x in have]
        if any('.' in r_ for r_ in raw):
            tol = max(tol, 0.05, 0.005 * max(abs(v) for v in vals))     # x100 fixed values: last digit
        else:
            tol = max(tol, 1)                                           # counts: +-1 is quantisation
        if k == 'v':
            for x in have:
                lo, hi = num(x.get('min')), num(x.get('max'))
                if lo is not None and hi is not None:
                    tol = max(tol, hi - lo)
        if max(vals) - min(vals) > tol:
            why.append('%s %s (tol %g)' % (k, '/'.join('%g' % v for v in vals), tol))
    return why


def runs_compare(paths, table=None, out=sys.stdout):
    """several NXSUITE.TXT files from one board + core -> the tests whose status differs, or whose v= or a
    numeric extra differs by more than the tolerance (the larger within-run max-min of the records, or
    RUN_TOL); returns the number of such tests. Refuses files from different cores or boards."""
    table = table or load_table()
    runs = []
    for p in paths:
        lines, _ = load_chain(p)
        res = parse(make_file(lines), table)
        h = {}
        for se in res['sessions']:
            h.update(se['header'])
        runs.append((p, h, res))
    for key in ('core', 'board', 'machine'):
        vals = {h.get(key) for _, h, _ in runs}
        if len(vals) > 1:
            raise Refused('the files differ in %s (%s): compare runs of one board and core only'
                          % (key, ', '.join(sorted(str(v) for v in vals))))
    bad = 0
    ids = sorted(set().union(*(set(r['tests']) for _, _, r in runs)))
    for tid in ids:
        recs = [r['tests'].get(tid) for _, _, r in runs]
        have = [x for x in recs if x and x['status'] not in ('SKIP', 'HANG-GUARD')]
        if len(have) < 2:
            continue
        why = diff_records(tid, have)
        if why:
            bad += 1
            print('%-8s differs between runs: %s' % (tid, '; '.join(why)), file=out)
    h = runs[0][1]
    print('(tolerance: the larger within-run min-max, a method resolution in RUN_TOL, +-1 for counts, '
          '0.5% or 0.05 for fixed-point values; SKIP and HANG-GUARD records left out)', file=out)
    srcs = [h.get('src') for _, h, _ in runs]
    if len(set(srcs)) > 1:
        print('builds differ (src %s): a test changed between builds can differ for that reason'
              % ' / '.join(str(x) for x in srcs), file=out)
    print('%d tests differ beyond tolerance across %d runs (core %s, board %s)' % (
        bad, len(runs), h.get('core'), h.get('board')), file=out)
    return bad


NOT_FINAL = ('SKIP', 'HANG-GUARD', 'PENDING-OPERATOR', 'VISUAL', 'VISUAL-SHOWN')


def _rec_name(D):
    pf = D.get('platform', {'kind': 'board'})
    if pf.get('kind', 'board') == 'board':
        return 'board %s, core %s' % (D['board']['name'], D['core'])
    return '%s (emulator; reports core %s)' % (pf['name'], D['core'])


def _test_order(table):
    gi = {g['id']: g['index'] for g in table['groups']}
    return sorted(table['tests'], key=lambda x: gi[x['group']])


def describe(tid=None, table=None, out=sys.stdout):
    """the plain description of one test (or every test): what an emulator author needs without the assembly"""
    table = table or load_table()
    gname = {g['id']: g['name'] for g in table['groups']}
    tests = [table['by_test'][tid.upper()]] if tid else _test_order(table)
    for x in tests:
        print('%s  %s  (group %s %s%s%s)' % (x['id'], x['title'], x['group'], gname[x['group']],
                                            ', operator' if x['operator'] else '', ', opt-in' if x['opt_in'] else ''),
              file=out)
        for c in x['claims']:
            cl = table['by_claim'].get(c, {})
            print('  claim %s: %s' % (c, cl.get('claim', '?')), file=out)
            print('    sources: %s' % ', '.join(cl.get('sources', [])), file=out)
        if 'left_out' in x:
            print('  LEFT OUT: %s' % x['left_out'], file=out)
        for k in ('purpose', 'method', 'expect', 'fields', 'needs', 'hazard'):
            if x.get(k):
                print('  %s: %s' % (k, x[k]), file=out)
        print('', file=out)
    return len(tests)


def _tcell(x):
    if not x:
        return 'not run'
    v = '%s %s' % (x.get('v'), x.get('u') if x.get('u') not in (None, '-') else '')
    ex = ' '.join('%s=%s' % kv_ for kv_ in list((x.get('extra') or {}).items())[:6])
    why = (x.get('extra') or {}).get('why')
    return ('%s %s%s' % (x['status'], v.strip(), (' (' + ex + ')') if ex and not why else
                         (' why=%s' % why if why else ''))).replace('|', '/')


def reference(paths, outdir, table=None):
    """the nxsuite test reference (Markdown) into OUTDIR: per group, per test, the description and every given
    record's result. Generated on demand, not kept in docs/: it is ~250 KB and changes with every record."""
    table = table or load_table()
    recs = [(p, json.load(open(p, encoding='utf-8'))) for p in paths]
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, 'nxsuite-test-reference.md')
    o = io.StringIO()
    o.write('# nxsuite test reference\n\nGenerated by `python tools/hwtests/intake.py --reference` (GPL-3.0-or-later, '
            'part of nexclash) from tools/hwtests/nxsuite_claims.json and the records below. "Expect" is what the '
            'sources predict; a result is what one record measured, labelled with its board and core. An emulator '
            'result is what that emulator does: never hardware evidence.\n\nRecords:\n\n')
    for p, D in recs:
        o.write('- %s: %s, suite build %s\n' % (os.path.basename(p), _rec_name(D), D['run'].get('src')))
    gname = {g['id']: g['name'] for g in table['groups']}
    last = None
    for x in _test_order(table):
        if x['group'] != last:
            last = x['group']
            o.write('\n## %s %s\n' % (x['group'], gname[x['group']]))
        o.write('\n### %s %s\n\n' % (x['id'], x['title']))
        for c in x['claims']:
            o.write('- Claim `%s`: %s\n' % (c, table['by_claim'].get(c, {}).get('claim', '?')))
        if 'left_out' in x:
            o.write('- LEFT OUT: %s\n' % x['left_out'])
        for k in ('purpose', 'method', 'expect', 'fields', 'needs', 'hazard'):
            if x.get(k):
                o.write('- %s: %s\n' % (k.capitalize(), x[k]))
        if recs and 'left_out' not in x:
            o.write('\n| Record | Result |\n|---|---|\n')
            for p, D in recs:
                o.write('| %s | %s |\n' % (_rec_name(D), _tcell(D['run']['tests'].get(x['id']))))
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(o.getvalue())
    return path


def conformance(emu, ref, table=None, out=sys.stdout):
    """one record (an emulator) against a reference record (a board): per test SAME / DIFFERENT / NOT COMPARABLE,
    by group, with the test's purpose and the tolerance (the --runs logic). -> {verdict: count}"""
    table = table or load_table()
    E, B = json.load(open(emu, encoding='utf-8')), json.load(open(ref, encoding='utf-8'))
    print('nxsuite conformance: %s against %s' % (_rec_name(E), _rec_name(B)), file=out)
    print('The reference is one machine: a difference means "differs from that board and core", not "wrong" '
          'everywhere; the emulator side is never hardware evidence.', file=out)
    if E['run'].get('src') != B['run'].get('src'):
        print('Builds differ (%s / %s): a test changed between builds can differ for that reason.'
              % (E['run'].get('src'), B['run'].get('src')), file=out)
    n = collections.Counter()
    gname = {g['id']: g['name'] for g in table['groups']}
    last = None
    for x in _test_order(table):
        if 'left_out' in x:
            continue
        if x['group'] != last:
            last = x['group']
            print('\n%s %s' % (x['group'], gname[x['group']]), file=out)
        e, b = E['run']['tests'].get(x['id']), B['run']['tests'].get(x['id'])
        purpose = (x.get('purpose') or x['title']).split('. ')[0].rstrip('.')
        nc = None
        for side, r in (('emulator', e), ('reference', b)):
            if not r:
                nc = '%s: not run%s' % (side, ' (opt-in group)' if x['opt_in'] else '')
            elif r['status'] in NOT_FINAL:
                w = (r.get('extra') or {}).get('why')
                nc = '%s: %s%s' % (side, r['status'], ' why=' + w if w else '')
            if nc:
                break
        if nc:
            n['NOT COMPARABLE'] += 1
            print('  %-5s NOT COMPARABLE  %s' % (x['id'], nc), file=out)
            continue
        why = diff_records(x['id'], [e, b])
        if not why:
            n['SAME'] += 1
            print('  %-5s SAME            %s' % (x['id'], purpose), file=out)
        else:
            n['DIFFERENT'] += 1
            print('  %-5s DIFFERENT       %s' % (x['id'], purpose), file=out)
            print('        emulator %s | reference %s: %s' % (_tcell(e), _tcell(b), '; '.join(why)), file=out)
    print('\n(tolerance as --runs: the larger within-run min-max, RUN_TOL, +-1 for counts, 0.5 % or 0.05 for '
          'fixed-point values; operator (V) tests compare only when both answered)', file=out)
    print('summary: %d SAME, %d DIFFERENT, %d NOT COMPARABLE' % (n['SAME'], n['DIFFERENT'], n['NOT COMPARABLE']),
          file=out)
    return n



def operator(h, table=None):
    """the session header's "H operator" answers (gq.asm) decoded with nxsuite_claims.json "platforms" -> dict,
    or None (a file from before the questionnaire). What the operator said, not a measurement."""
    if 'conn' not in h and 'model' not in h:
        return None
    table = table or load_table()
    pl = table.get('platforms', {})
    names = {p_['code']: p_['name'] for p_ in pl.get('list', [])}
    ans = pl.get('answers', {})
    out = {'model': None if h.get('model', '-') == '-' else h['model']}
    out['model_name'] = names.get(out['model']) if out['model'] else None
    for k in ('conn', 'disp', 'ramq', 'pi'):
        v = h.get(k, '-')
        out[k] = ans[k][int(v) - 1] if v.isdigit() and 0 < int(v) <= len(ans.get(k, [])) else None
    out['label'] = None if h.get('label', '-') == '-' else h['label']
    return out


def _nr(D, n):
    return (D['run'].get('nextregs') or {}).get('$%02X' % n)


def _t(D, tid, key='v'):
    x = D['run']['tests'].get(tid)
    if not x or x['status'] in NOT_FINAL:
        return None
    return x.get('v') if key == 'v' else (x.get('extra') or {}).get(key)


def identity(D):
    """the machine as one record measured it: [(item, value, source)]; values come from the launch NextReg
    snapshot (S01), the session header and tests; decoded only as far as a cited source says"""
    h = (D['run'].get('sessions') or [{}])[0]
    def nr(n):
        return _nr(D, n) or '?'
    rows = [('machine id (NextReg $00)', nr(0x00) + ' raw', 'S02; book ch 3 (report D-N17): $00 is the machine id')]
    b = nr(0x0F)
    rows.append(('board id (NextReg $0F)', b + (' = Issue 5' if b == '$03' else ' raw (only Issue 5 = $03 is stated)'),
                 'book ch 3 (report D-N17, B-N22)'))
    rows.append(('core version ($01 / $0E)', D.get('core', '?'), 'S02; book ch 1 L1533'))
    rows.append(('RAM (page 96)', '%s (%s)' % (h.get('ram', '?'), {
                 'wrap': 'not its own RAM; what 1 MB shows there is not stated',
                 'alias0': 'not its own RAM; what 1 MB shows there is not stated',
                 'distinct': 'its own RAM: more than 1 MB'}.get(h.get('ram'), 'no decode')),
                 'S03; docs/LEARNINGS.md:127'))
    rows.append(('machine timing (NextReg $03)', nr(0x03), 'docs/NEXT_REGISTERS.md:31 (bits 6:4)'))
    rows.append(('frame rate at start', '%s Hz ($05 = %s, bit 2)' % (h.get('hz', '?'), nr(0x05)),
                 'docs/NEXT_REGISTERS.md:32'))
    rows.append(('video timing (NextReg $11)', nr(0x11) + ' raw', 'no decode in the sources'))
    rows.append(('lines per frame / geometry', '%s / %s' % (h.get('lines', '?'), h.get('geom', '?')),
                 'F01; docs/TECHNIQUES.md:281'))
    rows.append(('CPU speed at start (NextReg $07)', nr(0x07), 'docs/NEXT_REGISTERS.md:36 (5:4 actual, 1:0 set)'))
    rows.append(('28 MHz read wait (NOP clocks)', str(_t(D, 'C01')), 'C01; book ch 2: 4 = none (3.03), 5 = 3.02'))
    rows.append(('CTC ticks per line x 100 / T per line',
                 '%s / %s' % (h.get('cal_ctc', '?'), h.get('t_per_line', '?')), 'header (G4 F02 method)'))
    rows.append(('DMA (blitter probe)', str(_t(D, 'D09')), 'D09; docs/DDMA.md:25, book N27'))
    rows.append(('internal port enables $82-$85', ' '.join(nr(n) for n in range(0x82, 0x86)),
                 'book N19 (L3234-3248)'))
    rows.append(('DivMMC ($0A, $B8-$BB)', ' '.join(nr(n) for n in (0x0A, 0xB8, 0xB9, 0xBA, 0xBB)),
                 'header H divmmc'))
    rows.append(('Pi / ESP / RTC', 'not probed', 'no safe documented read in the sources'))
    op = D.get('operator')
    if op:
        rows.append(('operator: machine', '%s %s' % (op.get('model') or '-', op.get('model_name') or ''),
                     'questionnaire (said, not measured)'))
        rows.append(('operator: display', '%s, %s' % (op.get('conn') or '-', op.get('disp') or '-'),
                     'questionnaire'))
        rows.append(('operator: RAM / Pi', '%s / %s' % (op.get('ramq') or '-', op.get('pi') or '-'),
                     'questionnaire'))
        rows.append(('operator: label', op.get('label') or '-', 'questionnaire (a machine nickname)'))
    return rows


def _facets(D):
    h = (D['run'].get('sessions') or [{}])[0]
    pf = D.get('platform', {'kind': 'board'})
    return {'platform': pf.get('kind', 'board') + ':' + (pf.get('name') or ''), 'board': D['board']['name'],
            'core': D.get('core'), 'video': '%s %s %s' % (h.get('hz'), h.get('geom'), h.get('timing'))}


def summary(paths, table=None, out=sys.stdout):
    """records of several machines / cores / emulators: the hardware identity side by side, then every test whose
    results differ beyond the --runs tolerance, grouped by what else differs between those records (board, core,
    video, platform); tests that differ only within tolerance are run-to-run noise. -> {test: facets}"""
    table = table or load_table()
    D = [json.load(open(p, encoding='utf-8')) for p in paths]
    names = [_rec_name(d) for d in D]
    print('# nxsuite summary\n\nRecords: ' + '; '.join('%d = %s' % (i + 1, n) for i, n in enumerate(names)),
          file=out)
    print('Emulator columns are what that emulator does, never hardware evidence; a one-board figure is that '
          'board and core only.', file=out)
    builds = [d['run'].get('src') for d in D]
    if len(set(builds)) > 1:
        print('Suite builds differ (%s): a test changed between builds can differ for that reason.'
              % ', '.join('%d %s' % (i + 1, b) for i, b in enumerate(builds)), file=out)
    print('\n## Hardware identity\n', file=out)
    print('| item | ' + ' | '.join(str(i + 1) for i in range(len(D))) + ' | source |', file=out)
    print('|---' * (len(D) + 2) + '|', file=out)
    ids = [identity(d) for d in D]
    items = []
    for r in ids:
        for it, _, src in r:
            if it not in [x[0] for x in items]:
                items.append((it, src))
    for it, src in items:
        cells = [next((v for i_, v, _ in r if i_ == it), '-') for r in ids]
        print('| %s | %s | %s |' % (it, ' | '.join(str(c).replace('|', '/') for c in cells), src), file=out)
    fac = [_facets(d) for d in D]
    groups, noise, same = collections.OrderedDict(), [], 0
    found = {}
    for x in _test_order(table):
        if 'left_out' in x:
            continue
        have = [(i, d['run']['tests'].get(x['id'])) for i, d in enumerate(D)]
        have = [(i, r) for i, r in have if r and r['status'] not in NOT_FINAL]
        if len(have) < 2:
            continue
        why = diff_records(x['id'], [r for _, r in have])
        if why:
            cl = []                                     # records that agree (within tolerance) together
            for i, r in have:
                for c in cl:
                    if not diff_records(x['id'], [c[0][1], r]):
                        c.append((i, r))
                        break
                else:
                    cl.append([(i, r)])
            keys = tuple(k for k in ('platform', 'board', 'core', 'video')
                         if all(len({fac[i][k] for i, _ in c}) == 1 for c in cl)
                         and len({fac[c[0][0]][k] for c in cl}) == len(cl)) or ('no single one',)
            part = ' | '.join(','.join(str(i + 1) for i, _ in c) for c in cl)
            groups.setdefault((part, keys), []).append((x, have, why))
            found[x['id']] = keys
        elif len({json.dumps([r.get('v'), r.get('extra')], sort_keys=True) for _, r in have}) > 1:
            noise.append(x['id'])
        else:
            same += 1
    print('\n## Results that differ (beyond the --runs tolerance)\n', file=out)
    for (part, keys), lst in sorted(groups.items(), key=lambda g: -len(g[1])):
        print('### %s (%d tests): the records on each side of a | agree; what sets the sides apart: %s\n'
              % (part, len(lst), ' + '.join(keys)), file=out)
        for x, have, why in lst:
            print('- %s %s: %s' % (x['id'], x['title'], '; '.join(
                '%d %s' % (i + 1, _tcell(r)) for i, r in have)), file=out)
            print('  (%s)' % '; '.join(why), file=out)
        print('', file=out)
    print('Run-to-run noise (values differ, within tolerance): %s' % (', '.join(noise) or 'none'), file=out)
    print('Same in every record that answered: %d tests. A difference where only the machine differs may be '
          'the machine or the run: repeat with --runs before reading it as a board difference.' % same, file=out)
    return found


def intake(path, board=None, outdir=OUTDIR, dry=False, out=sys.stdout, table=None, platform=None):
    table = table or load_table()
    lines, names = load_chain(path)
    data = make_file(lines)
    res = parse(data, table)
    res['parts'] = names
    p, doc = write_json(res, table, path, data, board, outdir, dry, platform)
    report(doc, table, out)
    print(('would write ' if dry else 'wrote ') + p, file=out)
    return doc


# ---------------------------------------------------------------- self-check (selftest --tools)
def make_file(body_lines):
    """Lines (no END) -> the bytes nxsuite writes: LF ends, END lines= crc16=."""
    body = ''.join(l + '\n' for l in body_lines).encode('ascii')
    return body + ('END lines=%d crc16=$%04X\n' % (len(body_lines), crc16(body))).encode('ascii')


def sample(table, fail=False):
    lines = ['NXSUITE 1',
             'H suite=1.0 src=00000000 built=2026-01-01 run=1 mode=ALL resumed_from=-',
             'H core=3.03.03 nr01=$33 nr0e=$03 machine=nr00:$0A board=nr0f:$02 ram=wrap',
             'H video=HDMI nr11=$07 timing=nr03:$33 hz=50 nr05=$5B lines=312 line_t=216',
             'H speed_start=nr07:$00 cal35=720 cal_ctc=108 t_per_line=216.18',
             'H divmmc nr0a=$11 nrb8=$82 nrb9=$00 nrba=$00 nrbb=$F2',
             'R nr=$00 v=$0A', 'G id=G0 name=SYS start',
             'T id=S05 st=%s c=sys-nextreg-keeps-select v=0 u=- n=1 min=0 max=0' % ('FAIL' if fail else 'PASS'),
             'T id=S01 st=INFO c=sys-launch-nextreg-state v=$DE u=- n=1 min=$DE max=$DE p7ffd=PASS',
             'T id=S03 st=INFO c=sys-ram-size v=wrap u=- n=1 min=wrap max=wrap',
             'T id=S07 st=HANG-GUARD c=sys-sd-write-rst8 v=- u=- n=0 min=- max=-',
             'G id=G0 end fails=0', 'G id=G4 name=FRAME start',
             'T id=F01 st=INFO c=frame-lines-50 v=311 u=lines n=1 min=311 max=311',
             'G id=G4 end fails=0', 'P pass=2 mode=G4', 'G id=G4 name=FRAME start',
             'T id=F01 st=INFO c=frame-lines-50 v=312 u=lines n=1 min=312 max=312',
             'T id=S03 st=SKIP c=sys-ram-size v=- u=- n=0 min=- max=- why=not-selected',
             'T id=F02 st=INFO c=frame-line-length v=216.1 u=T n=5 min=216 max=216.2',
             'T id=Z01 st=SKIP c=z80n-func-suite v=- u=- n=0 min=- max=- why=not-built',
             'T id=zf.MUL st=PASS c=z80n-func-suite f=$A5 fexp=$A5',
             'T id=zf.LDPIRX0 st=FAIL c=z80n-func-suite f=$00 fexp=$08 code=F',
             'T id=zf.LDIX0 st=FAIL c=z80n-func-suite f=$00 fexp=$08 code=F',
             'G id=G4 end fails=0']
    return lines


def selfcheck():
    """Made-up files: a good one, a truncated one, an unknown test id, a FAIL, a damaged byte; the negative
    control shows the damaged file is caught by the CRC check (accepted without it). -> failures"""
    bad = []
    table = load_table()
    good = make_file(sample(table))
    try:
        res = parse(good, table)
        v = verdicts(res, table)
        want = {'sys-nextreg-keeps-select': 'confirmed', 'sys-launch-7ffd-unlocked': 'confirmed',
                'sys-ram-size': 'choice', 'sys-sd-write-rst8': 'hung', 'frame-lines-50': 'measured',
                'frame-line-length': 'measured', 'z80n-func-suite': 'disproved', 'copper-wait-max-h': 'not-run',
                # sub-case claims: LDPIRX differs only in the unsure bits 5/3 -> confirmed with a note; the same
                # difference on LDIX disproves the LDIX claim (bits 5/3 are what that claim is about)
                'z80n-ldpirx-fixed': 'confirmed', 'z80n-ldix-flags': 'disproved', 'z80n-test-nf': 'not-run'}
        for c, w in want.items():
            if v[c]['verdict'] != w:
                bad.append('good file: %s %s, want %s' % (c, v[c]['verdict'], w))
        if v['frame-line-length']['spread'] != 0.1 or v['frame-lines-50']['value'] != 312:
            bad.append('good file: values %s' % v['frame-line-length'])
        if 'zf.MUL' not in res['subtests'].get('Z01', {}):
            bad.append('good file: sub-test zf.MUL not kept under Z01')
        if not v['z80n-ldpirx-fixed']['notes']:
            bad.append('good file: no note for the LDPIRX bits-5/3-only difference')
        if len(res['passes']) != 2 or [d[0] for d in passes_disagree(res)] != ['F01']:
            bad.append('passes: %s, disagree %s' % (res['passes'], passes_disagree(res)))
        # negative control: comparing every line, S03's SKIP in pass 2 would count as a disagreement
        if [d[0] for d in passes_disagree(res, final_only=False)] != ['F01', 'S03']:
            bad.append('negative control: all-lines disagree %s' % passes_disagree(res, final_only=False))
        if v['sys-ram-size']['choice'] is None and v['sys-ram-size']['verdict'] != 'choice':
            bad.append('S03 SKIP in a later pass replaced its answer: %s' % v['sys-ram-size'])
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, 'NXSUITE.TXT')
            open(src, 'wb').write(good)
            p, doc = write_json(res, table, src, good, None, d)
            p2, doc2 = write_json(res, table, src, good, None, d)
            if p != p2 or doc2['intake_runs'] != 2 or not os.path.basename(p).startswith('issue4-compatible-3.03.03'):
                bad.append('json: %s runs %s' % (p, doc2['intake_runs']))
            res_f = parse(make_file(sample(table, fail=True)), table)
            pf, docf = write_json(res_f, table, src, good, 'other', d)
            if docf['claims']['sys-nextreg-keeps-select']['verdict'] != 'disproved':
                bad.append('a FAIL is not disproved')
            import io
            if compare(p, pf, out=io.StringIO()) != 1:
                bad.append('--compare does not list exactly the one changed claim')
            pe, doce = write_json(res, table, src, good, None, d, platform='JNext 1.3.0')
            if os.path.dirname(pe) != os.path.join(d, 'emulator') or doce['platform']['hardware_evidence']:
                bad.append('emulator results not kept apart: %s' % pe)
            o = io.StringIO()
            compare(p, pe, out=o)
            if 'board vs emulator' not in o.getvalue():
                bad.append('--compare does not mark board vs emulator')
            if conformance(p, p, table, out=io.StringIO())['DIFFERENT'] != 0:
                bad.append('--conformance finds differences between a record and itself')
            nc = conformance(pf, p, table, out=io.StringIO())
            if nc['DIFFERENT'] != 1:
                bad.append('--conformance does not find exactly the one changed test (%s)' % dict(nc))
            if describe('S05', table, out=io.StringIO()) != 1:
                bad.append('--describe')
            rp = reference([p, pe], d, table)
            if '### S05' not in open(rp, encoding='utf-8').read():
                bad.append('--reference has no S05 section')
    except Refused as e:
        bad.append('good file refused: %s' % e)
    cases = {'truncated': good[:len(good) - 30],
             'no END line': make_file(sample(table))[:-len(make_file(sample(table)).split(b'\n')[-2]) - 1],
             'unknown test id': make_file(sample(table) + ['T id=Q99 st=PASS c=x v=1 u=- n=1 min=1 max=1']),
             'unknown status': make_file(sample(table) + ['T id=S00 st=MAYBE c=x v=1']),
             'CR line ends': good.replace(b'\n', b'\r\n')}
    i = good.index(b'v=312')
    damaged = good[:i] + b'v=313' + good[i + 5:]
    cases['damaged byte'] = damaged
    for name, data in cases.items():
        try:
            parse(data, table)
            bad.append('%s: accepted' % name)
        except Refused:
            pass
    # negative control: without the CRC check the damaged file passes (so it is the CRC that catches it)
    try:
        parse(damaged, table, check_crc=False)
    except Refused as e:
        bad.append('negative control: the damaged file is refused even without the CRC check (%s)' % e)
    # parts: a session split into NXSUITE.001 + NXSUITE.TXT (C line) joins back to the same lines
    whole = sample(table)
    cut = len(whole) // 2
    src = kv(whole[1].split()[1:], 2)['src']
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, 'NXSUITE.001'), 'wb').write(make_file(whole[:cut]))
        open(os.path.join(d, 'NXSUITE.TXT'), 'wb').write(
            make_file(['NXSUITE 1', 'C part=001 src=%s' % src] + whole[cut:]))
        try:
            lines, names = load_chain(os.path.join(d, 'NXSUITE.TXT'))
            if lines != whole or names != ['NXSUITE.001', 'NXSUITE.TXT']:
                bad.append('parts: joined %s, not the whole file' % names)
        except Refused as e:
            bad.append('parts refused: %s' % e)
        os.remove(os.path.join(d, 'NXSUITE.001'))
        try:
            load_chain(os.path.join(d, 'NXSUITE.TXT'))
            bad.append('parts: a missing part was accepted')
        except Refused:
            pass
        try:
            parse(make_file(['NXSUITE 1', 'C part=001 src=%s' % src] + whole[cut:]), table)
            bad.append('parts: a continuation read alone was accepted')
        except Refused:
            pass
    try:
        r = parse(make_file(whole + ['X truncated lost=99']), table)
        if r['truncated'] != '99':
            bad.append('X truncated not reported: %s' % r['truncated'])
    except Refused as e:
        bad.append('X truncated file refused: %s' % e)
    # --runs: two runs of one board + core; F02 within tolerance, S05 status and F01 value differ -> 2
    with tempfile.TemporaryDirectory() as d:
        a_, b_ = os.path.join(d, 'a.txt'), os.path.join(d, 'b.txt')
        open(a_, 'wb').write(make_file(whole))
        alt = [l.replace('st=PASS c=sys-nextreg-keeps-select', 'st=FAIL c=sys-nextreg-keeps-select')
               .replace('v=312 u=lines n=1 min=312 max=312', 'v=315 u=lines n=1 min=315 max=315')
               .replace('v=216.1 u=T', 'v=216.12 u=T') for l in whole]
        open(b_, 'wb').write(make_file(alt))
        sink = io.StringIO()
        n_ = runs_compare([a_, b_], table, out=sink)
        if n_ != 2:
            bad.append('--runs: %d tests flagged, expected 2 (%s)' % (n_, sink.getvalue().strip()))
        # --summary: two made-up boards (the same file, the second with S05 / F01 changed, F02 within
        # tolerance, another board name, an operator line with a label): S05 + F01 differ (platform = the machine
        # answered, and board), F02 is noise
        ra = parse(make_file(whole), table)
        k_ = next(i for i, l in enumerate(alt) if l.startswith('H divmmc')) + 1
        rb = parse(make_file(alt[:k_] + ['H operator model=K3 conn=2 disp=1 ramq=2 pi=3 label=BENCH2'] + alt[k_:]),
                   table)
        pa_, _ = write_json(ra, table, a_, b'a', 'made-up-a', d)
        pb_, docb = write_json(rb, table, b_, b'b', 'made-up-b', d)
        if not pb_.endswith('made-up-b-3.03.03-bench2.json') or not pa_.endswith('made-up-a-3.03.03.json'):
            bad.append('record names %s / %s (label in the name only when given)' % (pa_, pb_))
        if (docb.get('operator') or {}).get('model_name') != 'KS3 Next (Artix-7 35T)':
            bad.append('operator answers not decoded: %s' % docb.get('operator'))
        # the platform name: the operator's machine answer names it; registers alone only say "compatible"
        pc_, docc = write_json(rb, table, b_, b'b', None, d, dry=True)
        pr_, docr = write_json(ra, table, a_, b'a', None, d, dry=True)
        if (not pc_.endswith('next-ks3-3.03.03-bench2.json') or docc['board']['named_from'] != 'operator'
                or not os.path.basename(pr_).startswith('issue4-compatible-')
                or docr['board']['named_from'] != 'registers'):
            bad.append('platform names %s / %s' % (pc_, pr_))
        sink = io.StringIO()
        f_ = summary([pa_, pb_], table, out=sink)
        if sorted(f_) != ['F01', 'S05'] or f_['F01'] != ('platform', 'board') or 'F02' not in sink.getvalue().split(
                'noise')[-1] or 'BENCH2' not in sink.getvalue():
            bad.append('--summary: %s (want F01 + S05 by board, F02 noise, the label shown)' % f_)
        # negative control: a summary blind to differences finds nothing - the check above would catch it
        keep = diff_records
        try:
            globals()['diff_records'] = lambda t, h: []
            if summary([pa_, pb_], table, out=io.StringIO()):
                bad.append('negative control: --summary found differences with the comparison switched off')
        finally:
            globals()['diff_records'] = keep
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file', nargs='?')
    ap.add_argument('--board', help='board name for the output file (default: from NextReg $0F)')
    ap.add_argument('--platform', default='board',
                    help='"board" (default) or the emulator name and exact version, e.g. "JNext 1.3.0"')
    ap.add_argument('--out', default=OUTDIR, help='output folder (default docs/kb/hardware)')
    ap.add_argument('--dry-run', action='store_true', help='report only, write nothing')
    ap.add_argument('--compare', nargs=2, metavar=('A', 'B'))
    ap.add_argument('--runs', nargs='+', metavar='TXT',
                    help='two or more NXSUITE.TXT files of one board + core: list the tests whose values differ '
                         'beyond tolerance (unstable)')
    ap.add_argument('--describe', nargs='?', const='', metavar='TEST',
                    help='print the plain description of TEST (or of every test)')
    ap.add_argument('--reference', nargs='*', metavar='JSON',
                    help='write nxsuite-test-reference.md into --out (default: the current folder) with the results '
                         'of these records')
    ap.add_argument('--summary', nargs='+', metavar='JSON',
                    help='records side by side: hardware identity, then the results that differ, grouped')
    ap.add_argument('--conformance', metavar='EMU_JSON', help='a record against --against REF_JSON (a board)')
    ap.add_argument('--against', metavar='REF_JSON')
    ap.add_argument('--selfcheck', action='store_true')
    a = ap.parse_args(argv)
    if a.selfcheck:
        b = selfcheck()
        print('intake selfcheck: %s' % ('OK' if not b else 'FAIL %s' % b))
        return 1 if b else 0
    if a.describe is not None:
        try:
            describe(a.describe or None)
        except KeyError:
            print('no test %s' % a.describe)
            return 2
        return 0
    if a.reference is not None:
        print('wrote %s' % reference(a.reference, a.out if a.out != OUTDIR else '.'))
        return 0
    if a.summary:
        summary(a.summary)
        return 0
    if a.conformance:
        if not a.against:
            ap.error('--conformance needs --against REF_JSON')
        conformance(a.conformance, a.against)
        return 0
    if a.compare:
        compare(*a.compare)
        return 0
    if a.runs:
        if len(a.runs) < 2:
            ap.error('--runs needs two or more files')
        try:
            return 1 if runs_compare(a.runs) else 0
        except Refused as e:
            print('REFUSED: %s' % e)
            return 2
    if not a.file:
        ap.error('give NXSUITE.TXT, --compare A B or --selfcheck')
    try:
        intake(a.file, a.board, a.out, a.dry_run, platform=a.platform)
    except Refused as e:
        print('REFUSED: %s' % e)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
