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
import datetime
import hashlib
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
              ('I13', 'irq-ctc-time-constant'): 'choice'}


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
    t = json.load(open(path))
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
    return res


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


def passes_disagree(res):
    """tests run in more than one pass whose status, value or extras differ -> [(id, [(pass, summary)])]"""
    out = []

    def summ(r):
        return '%s v=%s %s' % (r['status'], r.get('v', '-'),
                               ' '.join('%s=%s' % kv_ for kv_ in sorted(r['extra'].items())))
    for tid, hist in sorted(res['history'].items()):
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
        st = [r['status'] for r in recs]
        if 'HANG-GUARD' in st:
            v['verdict'], v['why'] = 'hung', 'the machine stopped in %s' % ','.join(
                r['id'] for r in recs if r['status'] == 'HANG-GUARD')
        elif all(s in ('SKIP', 'PENDING-OPERATOR', 'VISUAL-SHOWN', 'VISUAL') for s in st):
            v['verdict'] = 'pending-operator' if 'PENDING-OPERATOR' in st else 'not-run'
            v['why'] = ','.join('%s:%s' % (r['id'], r.get('why', r['status'].lower())) for r in recs)
        else:
            done = [r for r in recs if r['status'] in ('PASS', 'FAIL', 'INFO', 'OPERATOR')]
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
        out[cid] = v
    return out


ISSUES = {'00': 'issue2', '01': 'issue3', '02': 'issue4'}     # NextReg $0F board id on a Next ($00 = $0A)


def board_name(res, board=None):
    """--board, else from NextReg $00 / $0F: a Next ($00 = $0A) -> next-issue2 / 3 / 4 (Issue 2 = the KS1
    boards); anything else -> machine-xx-board-yy"""
    h = res['sessions'][0]['header']
    if board:
        return board
    m = h.get('machine', 'nr00:$00').split(':')[-1].lstrip('$').lower()
    b = h.get('board', 'nr0f:$00').split(':')[-1].lstrip('$').lower()
    if m == '0a' and b in ISSUES:
        return 'next-' + ISSUES[b]
    return 'machine-%s-board-%s' % (m, b)


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
    if is_board(platform):
        path = os.path.join(outdir, '%s-%s.json' % (board_name(res, board), core))
    else:
        path = os.path.join(outdir, 'emulator', '%s-%s.json' % (slug(platform), core))
    old = json.load(open(path)) if os.path.exists(path) else {}
    sha = hashlib.sha256(data).hexdigest()
    hist = old.get('intakes', [])
    hist.append({'date': datetime.date.today().isoformat(), 'file_sha256': sha})
    v = verdicts(res, table)
    doc = {'schema': 2,
           'platform': {'kind': 'board' if is_board(platform) else 'emulator',
                        'name': 'board' if is_board(platform) else platform,
                        'hardware_evidence': is_board(platform)},
           'board': {'name': board_name(res, board) if is_board(platform) else slug(platform),
                     'nr00': h.get('machine', ''), 'nr0f': h.get('board', ''),
                     'ram': h.get('ram'), 'video': h.get('video'), 'geom': h.get('geom')},
           'core': core, 'intake_runs': len(hist), 'intakes': hist,
           'run': {'suite': h.get('suite'), 'src': h.get('src'), 'file': os.path.basename(path_in),
                   'file_sha256': sha, 'sessions': [s['header'] for s in res['sessions']],
                   'nextregs': res['nextregs'], 'tests': res['tests'], 'subtests': res['subtests'],
                   'comments': res['comments'], 'passes': res['passes'],
                   'parts': res.get('parts', []), 'truncated': res['truncated'],
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
             'pending-operator': 6, 'not-run': 7}
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
        else:
            what = 'NOT ANSWERED (%s: %s)' % (x['verdict'], x['why'])
        print('%-34s %s  [%s]' % (cid, what.strip(), ','.join(x['tests'])), file=out)
        if x['verdict'] in ('confirmed', 'disproved', 'measured', 'choice', 'operator'):
            vals = '; '.join('%s: %s' % (k, s) for k, s in c['values'].items())
            print('    expected  %s' % vals, file=out)
            print('    sources   %s' % ', '.join(c['sources']), file=out)
            for nt in x.get('notes', []):
                print('    note      %s' % nt, file=out)
    n = {}
    for x in v.values():
        n[x['verdict']] = n.get(x['verdict'], 0) + 1
    print('summary: ' + ', '.join('%s %d' % kv_ for kv_ in sorted(n.items())), file=out)
    dis = doc['run'].get('passes_disagree', [])
    if dis:
        print('passes disagree (%d tests; the verdict used the latest pass):' % len(dis), file=out)
        for d in dis:
            print('  %s' % d['id'], file=out)
            for r in d['records']:
                print('    pass %d: %s' % (r['pass'], r['result']), file=out)
    print('(nothing was changed in lessons or docs: apply the results in a reviewed change)', file=out)


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
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, 'NXSUITE.TXT')
            open(src, 'wb').write(good)
            p, doc = write_json(res, table, src, good, None, d)
            p2, doc2 = write_json(res, table, src, good, None, d)
            if p != p2 or doc2['intake_runs'] != 2 or not os.path.basename(p).startswith('next-issue4-3.03.03'):
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
    ap.add_argument('--selfcheck', action='store_true')
    a = ap.parse_args(argv)
    if a.selfcheck:
        b = selfcheck()
        print('intake selfcheck: %s' % ('OK' if not b else 'FAIL %s' % b))
        return 1 if b else 0
    if a.compare:
        compare(*a.compare)
        return 0
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
