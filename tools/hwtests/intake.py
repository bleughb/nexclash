"""Load an nxsuite result file (NXSUITE.TXT) into the repository's hardware results (GPL-3.0-or-later, part of nexclash).

    python tools/hwtests/intake.py NXSUITE.TXT [--board NAME] [--out DIR] [--dry-run]
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
"""
import argparse
import datetime
import hashlib
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TABLE = os.path.join(HERE, 'nxsuite_claims.json')
OUTDIR = os.path.join(ROOT, 'docs', 'kb', 'hardware')
STATUSES = {'PASS', 'FAIL', 'INFO', 'SKIP', 'HANG-GUARD', 'VISUAL', 'VISUAL-SHOWN', 'OPERATOR', 'PENDING-OPERATOR'}
# multi-claim tests: the extra key that decides one of their claims (the test's own status decides the rest)
CLAIM_KEYS = {('S01', 'sys-launch-7ffd-unlocked'): 'p7ffd'}


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


def parse(data, table, check_crc=True):
    """bytes -> dict(sessions, nextregs, tests {id: record}, groups, lines). Raises Refused."""
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
    res = {'sessions': [], 'nextregs': {}, 'tests': {}, 'groups': {}, 'subtests': {}, 'comments': []}
    cur = None
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
            if cur is None:
                raise Refused('line %d: H line before the first "H suite=" line' % n)
            cur['header'].update({k: v for k, v in f.items() if v is not True})
        elif rec == 'R':
            if 'nr' not in f or 'v' not in f:
                raise Refused('line %d: R line without nr= / v=' % n)
            res['nextregs'][f['nr'].upper()] = f['v'].upper()
        elif rec == 'G':
            if 'id' not in f:
                raise Refused('line %d: G line without id=' % n)
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
            r = {'id': tid, 'status': st, 'line': n}
            for k in ('v', 'u', 'n', 'min', 'max', 'why', 'exp', 'c'):
                if k in f:
                    r[k] = f[k]
            r['extra'] = {k: v for k, v in f.items() if k not in r and k not in ('id', 'st') and v is not True}
            if parent:
                res['subtests'].setdefault(parent, {})[tid] = r
            else:
                res['tests'][tid] = r          # the last line written wins
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


def verdicts(res, table):
    """-> {claim: {verdict, value, spread, unit, choice, tests, why}}"""
    out = {}
    for c in table['claims']:
        cid = c['id']
        tests = [x['id'] for x in table['tests'] if cid in x['claims']]
        recs = [res['tests'][t] for t in tests if t in res['tests']]
        v = {'verdict': 'not-run', 'tests': tests, 'value': None, 'spread': None, 'unit': c['unit'], 'choice': None,
             'why': None, 'result_type': c['result_type']}
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
            r0 = done[0]
            val, lo, hi = num(r0.get('v')), num(r0.get('min')), num(r0.get('max'))
            if val is not None:
                v['value'] = val
                if lo is not None and hi is not None:
                    v['spread'] = round((hi - lo) / 2, 2)
            else:
                v['choice'] = v['choice'] or r0.get('v')
            v['unit'] = r0.get('u') if r0.get('u') not in (None, '-') else c['unit']
        out[cid] = v
    return out


def board_name(res, board=None):
    h = res['sessions'][0]['header']
    if board:
        return board
    return 'board-%s' % h.get('board', 'nr0f:$00').split(':')[-1].lstrip('$').lower()


def write_json(res, table, path_in, data, board=None, outdir=OUTDIR, dry=False):
    h = res['sessions'][0]['header']
    core = h.get('core', 'unknown')
    for s in res['sessions'][1:]:
        if s['header'].get('core') not in (None, core):
            raise Refused('the file mixes cores %s and %s: run the intake per core' % (core, s['header']['core']))
    name = '%s-%s' % (board_name(res, board), core)
    path = os.path.join(outdir, name + '.json')
    old = json.load(open(path)) if os.path.exists(path) else {}
    sha = hashlib.sha256(data).hexdigest()
    hist = old.get('intakes', [])
    hist.append({'date': datetime.date.today().isoformat(), 'file_sha256': sha})
    v = verdicts(res, table)
    doc = {'schema': 1,
           'board': {'name': board_name(res, board), 'nr00': h.get('machine', ''), 'nr0f': h.get('board', ''),
                     'ram': h.get('ram'), 'video': h.get('video')},
           'core': core, 'intake_runs': len(hist), 'intakes': hist,
           'run': {'suite': h.get('suite'), 'src': h.get('src'), 'file': os.path.basename(path_in),
                   'file_sha256': sha, 'sessions': [s['header'] for s in res['sessions']],
                   'nextregs': res['nextregs'], 'tests': res['tests'], 'subtests': res['subtests'],
                   'comments': res['comments']},
           'claims': v}
    if not dry:
        os.makedirs(outdir, exist_ok=True)
        with open(path, 'w', newline='\n') as fh:
            json.dump(doc, fh, indent=1, sort_keys=False)
            fh.write('\n')
    return path, doc


def report(doc, table, out=sys.stdout):
    v = doc['claims']
    order = {'disproved': 0, 'hung': 1, 'confirmed': 2, 'measured': 3, 'choice': 4, 'operator': 5,
             'pending-operator': 6, 'not-run': 7}
    print('board %s  core %s  (intake run %d)' % (doc['board']['name'], doc['core'], doc['intake_runs']), file=out)
    for cid in sorted(v, key=lambda c: (order.get(v[c]['verdict'], 9), c)):
        x, c = v[cid], table['by_claim'][cid]
        if x['verdict'] == 'confirmed':
            what = 'CONFIRMED'
        elif x['verdict'] == 'disproved':
            what = 'DISPROVED'
        elif x['verdict'] in ('measured', 'choice', 'operator'):
            if x['value'] is not None:
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
    n = {}
    for x in v.values():
        n[x['verdict']] = n.get(x['verdict'], 0) + 1
    print('summary: ' + ', '.join('%s %d' % kv_ for kv_ in sorted(n.items())), file=out)
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
    print('%d claims differ between %s (%s %s) and %s (%s %s)' % (
        diff, os.path.basename(a), A['board']['name'], A['core'], os.path.basename(b), B['board']['name'],
        B['core']), file=out)
    return diff


def intake(path, board=None, outdir=OUTDIR, dry=False, out=sys.stdout, table=None):
    table = table or load_table()
    data = open(path, 'rb').read()
    res = parse(data, table)
    p, doc = write_json(res, table, path, data, board, outdir, dry)
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
             'T id=F01 st=INFO c=frame-lines-50 v=312 u=lines n=1 min=312 max=312',
             'T id=F02 st=INFO c=frame-line-length v=216.1 u=T n=5 min=216 max=216.2',
             'T id=Z01 st=SKIP c=z80n-func-suite v=- u=- n=0 min=- max=- why=not-built',
             'T id=zf.MUL st=PASS c=z80n-func-suite f=$A5 fexp=$A5',
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
                'frame-line-length': 'measured', 'z80n-func-suite': 'not-run', 'copper-wait-max-h': 'not-run'}
        for c, w in want.items():
            if v[c]['verdict'] != w:
                bad.append('good file: %s %s, want %s' % (c, v[c]['verdict'], w))
        if v['frame-line-length']['spread'] != 0.1 or v['frame-lines-50']['value'] != 312:
            bad.append('good file: values %s' % v['frame-line-length'])
        if 'zf.MUL' not in res['subtests'].get('Z01', {}):
            bad.append('good file: sub-test zf.MUL not kept under Z01')
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, 'NXSUITE.TXT')
            open(src, 'wb').write(good)
            p, doc = write_json(res, table, src, good, None, d)
            p2, doc2 = write_json(res, table, src, good, None, d)
            if p != p2 or doc2['intake_runs'] != 2 or not os.path.basename(p).startswith('board-02-3.03.03'):
                bad.append('json: %s runs %s' % (p, doc2['intake_runs']))
            res_f = parse(make_file(sample(table, fail=True)), table)
            pf, docf = write_json(res_f, table, src, good, 'other', d)
            if docf['claims']['sys-nextreg-keeps-select']['verdict'] != 'disproved':
                bad.append('a FAIL is not disproved')
            import io
            if compare(p, pf, out=io.StringIO()) != 1:
                bad.append('--compare does not list exactly the one changed claim')
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
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file', nargs='?')
    ap.add_argument('--board', help='board name for the output file (default: from NextReg $0F)')
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
        intake(a.file, a.board, a.out, a.dry_run)
    except Refused as e:
        print('REFUSED: %s' % e)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
