"""Research database: one small JSON per analysed game, so the next game starts from what is known.

    python -m nexclash.kb add SURVEY_DIR --game NAME [--title T] [--model M] [--outcome O] [--note N]
    python -m nexclash.kb find WORD [WORD ...]      games whose entry holds every word (model, engine, title ...)
    python -m nexclash.kb match SURVEY_DIR          routines of a new survey that resemble a known game's
    python -m nexclash.kb hw WORD                   Spectrum hardware / ROM lookup (docs/kb/hardware.json)
    python -m nexclash.kb list                      one line per game
    python -m nexclash.kb seed [--reference DIR] [--stop N] [--only REC]   maintainers: entries for the
                                                    recorded games whose reference files are present

Entries: docs/kb/games/<game>.json (facts only: addresses, counts, routine fingerprints - never game
bytes). `add` reads survey.json (python -m nexclash.survey) and keeps the hand-written fields of an
existing entry (title, model, outcome, design, notes). Analysed-but-not-converted games belong here
too (outcome "skipped: why"): the finding is the value.

Fingerprint of a routine: its first instructions with every number replaced by N (so the same
routine at another address or with other tables matches), as hashes of 6-instruction windows.
`match` scores two routines by shared windows (Jaccard); >= 0.5 is worth a look, 1.0 is the same
code. Engines were reused across games (Dizzy, Ultimate, Don Priestley ...): a match turns an
unknown engine into a known family before any disassembly is read.

No game's dependency (docs/records): changing this module re-verifies nothing.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = os.path.join(ROOT, 'docs', 'kb')
GAMES = os.path.join(KB, 'games')
WINDOW, MAX_INS = 6, 96
KEEP = ('title', 'publisher', 'author', 'year', 'model', 'outcome', 'design', 'cards', 'notes', 'family')


def _disassembler(mem):
    from skoolkit.disassembler import Disassembler
    cfg = SimpleNamespace(defb_size=8, defm_size=65, defw_size=1, handle_rst=False, wrap=False, opcodes='',
                          asm_hex=True, asm_lower=False,
                          imaker=lambda a, o, b: SimpleNamespace(address=a, operation=o, bytes=b))
    return Disassembler(list(mem), cfg)


def masked(mem, addr, limit=MAX_INS, dis=None):
    """-> the routine's instructions from addr with numbers masked, to its first unconditional exit."""
    dis = dis or _disassembler(mem)
    out, a = [], addr
    while len(out) < limit and 0x4000 <= a < 0x10000:
        try:
            ins = dis.disassemble(a, a + 1, 'd')[0]
        except Exception:                                   # noqa: BLE001 - data, not code
            break
        op = ins.operation
        out.append(re.sub(r'\$[0-9A-F]+|\b\d+\b', 'N', re.sub(r'\b(BIT|SET|RES) \d', r'\1 b', op)))
        a += len(ins.bytes)
        if op in ('RET', 'RETI', 'RETN') or op.startswith(('JP $', 'JP (', 'JR $')) and ',' not in op:
            break
    return out


def fingerprint(mem, addr, dis=None):
    """-> {'n': instructions, 'full': hash of all, 'win': sorted window hashes} (no game bytes)."""
    ins = masked(mem, addr, dis=dis)
    h = lambda xs: hashlib.sha1('|'.join(xs).encode()).hexdigest()[:10]
    win = sorted({h(ins[i:i + WINDOW]) for i in range(max(1, len(ins) - WINDOW + 1))})
    return {'n': len(ins), 'full': h(ins), 'win': win}


def similarity(f, g):
    a, b = set(f.get('win', [])), set(g.get('win', []))
    return len(a & b) / len(a | b) if a and b else 0.0


def entries():
    out = {}
    for p in sorted(glob.glob(os.path.join(GAMES, '*.json'))):
        out[os.path.splitext(os.path.basename(p))[0]] = json.load(open(p))
    return out


def match(routines, skip=None, floor=0.5, min_ins=8, z80=None):
    """routines: survey.json 'routines' (with 'fingerprint'). -> [(score, routine, game, their routine, role)]."""
    hits = []
    for game, e in entries().items():
        if game == skip or z80 and e.get('inputs', {}).get('z80') == z80:    # the same game is no finding
            continue
        for theirs in e.get('routines', []):
            g = theirs.get('fingerprint') or {}
            for mine in routines:
                f = mine.get('fingerprint') or {}
                if min(f.get('n', 0), g.get('n', 0)) < min_ins:
                    continue                                # a 3-instruction stub matches everything
                s = 1.0 if f.get('full') == g.get('full') else similarity(f, g)
                if s >= floor:
                    hits.append((round(s, 2), mine['routine'], game, theirs['routine'], theirs.get('role', '')))
    return sorted(hits, key=lambda h: (-h[0], str(h[1])))


def from_survey(js, old=None):
    """survey.json -> a kb entry; hand-written fields of `old` are kept."""
    f = js.get('findings', {})
    e = {'game': js.get('game'), 'schema': 1, 'machine': js.get('machine'), 'engine': js.get('engine'),
         'inputs': js.get('inputs', {}), 'frames': js.get('frames'),
         'model': f.get('model'), 'pacing': f.get('pacing'), 'interrupts_accepted': f.get('interrupts_accepted'),
         'source_buffers': f.get('sources', {}), 'coverage_gaps': js.get('coverage_gaps'),
         'plain': js.get('plain'), 'outcome': 'analysed', 'routines': []}
    for r in js.get('routines', []):
        if not isinstance(r.get('routine'), int):
            continue
        e['routines'].append({k: r.get(k) for k in ('routine', 'role', 'pixel_bytes', 'attr_bytes', 'block_copy_bytes',
                                                    'calls', 'T_median', 'fingerprint') if r.get(k) is not None}
                             | {'callers': len(r.get('callers_seen', {}))})
    for k in KEEP:
        if old and old.get(k) not in (None, '', []):
            e[k] = old[k]
    if old:                                                 # roles written by hand survive a re-survey
        roles = {r['routine']: r['role'] for r in old.get('routines', []) if r.get('role')}
        for r in e['routines']:
            if roles.get(r['routine']):
                r['role'] = roles[r['routine']]
    return e


def seed(reference, stop=3000, only=None, log=print):
    """Entries for docs/records games from their reference snapshot + first .rzx (survey --full --stop).
    Existing entries are kept unless named with `only`. -> (written, skipped: {record: why})."""
    import tempfile
    from . import survey as S
    done, skipped = [], {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'docs', 'records', '*.json'))):
        rec = json.load(open(p))
        name = re.sub(r'[^a-z0-9_]', '_', os.path.splitext(os.path.basename(p))[0].lower())
        dest = os.path.join(GAMES, name + '.json')
        if only and name not in only or not only and os.path.exists(dest):
            continue
        inp = rec.get('inputs', {})
        z = os.path.join(reference, (inp.get('snapshot') or {}).get('path', '?'))
        rz = [os.path.join(reference, r['path']) for r in inp.get('recordings', []) if r.get('path', '').lower().endswith('.rzx')]
        rz = [r for r in rz if os.path.exists(r)][:1]
        if not os.path.exists(z) or not z.lower().endswith('.z80') or not rz:
            skipped[name] = 'no reference .z80 + .rzx here'
            continue
        try:
            with tempfile.TemporaryDirectory() as tmp:
                _, js = S.survey(z, rz, tmp, stop=stop, log=lambda m: None, full=True)
        except Exception as e:                              # noqa: BLE001 - one game must not stop the rest
            skipped[name] = 'survey failed: %s' % str(e)[:80]
            continue
        e = from_survey(js, json.load(open(dest)) if os.path.exists(dest) else None)
        e.update(game=name, title=rec.get('game'), engine=rec.get('engine') or e.get('engine'),
                 outcome='converted (docs/records/%s)' % os.path.basename(p), doc=rec.get('doc'))
        os.makedirs(GAMES, exist_ok=True)
        json.dump(e, open(dest, 'w', newline='\n'), indent=1)
        done.append(name)
        log(_line(name, e))
    return done, skipped


def _line(g, e):
    return '%-34s %-5s model=%s; pacing=%s; engine=%s; outcome=%s' % (
        g, e.get('machine') or '?', e.get('model') or '?', e.get('pacing') or '?', e.get('engine') or '-', e.get('outcome') or '?')


def hw(words):
    d = json.load(open(os.path.join(KB, 'hardware.json')))
    ws = [w.lower().lstrip('$').replace('0x', '') for w in words]
    out = []
    for sect, items in d.items():
        if sect.startswith('_'):
            continue
        for it in items:
            text = json.dumps(it).lower()
            if all(w in text for w in ws):
                out.append('%-8s %s' % (sect, '  '.join('%s' % v for v in it.values())))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    a_ = sub.add_parser('add')
    a_.add_argument('survey_dir')
    a_.add_argument('--game', required=True, help='entry name = games/<game>.md name (lower case, underscores)')
    for k in ('title', 'model', 'outcome', 'family'):
        a_.add_argument('--' + k)
    a_.add_argument('--note', action='append')
    f_ = sub.add_parser('find')
    f_.add_argument('words', nargs='+')
    m_ = sub.add_parser('match')
    m_.add_argument('survey_dir')
    h_ = sub.add_parser('hw')
    h_.add_argument('words', nargs='+')
    sub.add_parser('list')
    s_ = sub.add_parser('seed')
    s_.add_argument('--reference', default=os.environ.get('NEXCLASH_REFERENCE') or os.path.join(ROOT, '..', 'specnext', 'reference'))
    s_.add_argument('--stop', type=int, default=3000)
    s_.add_argument('--only', action='append')
    a = ap.parse_args(argv)
    if a.cmd == 'add':
        if not re.fullmatch(r'[a-z0-9_]+', a.game):
            sys.exit('kb: --game is lower case, digits, underscores (CLAUDE.md names)')
        js = json.load(open(os.path.join(a.survey_dir, 'survey.json')))
        if js.get('mode') != 'full':
            sys.exit('kb: recognition-only survey has no facts - run the survey with --full')
        os.makedirs(GAMES, exist_ok=True)
        p = os.path.join(GAMES, a.game + '.json')
        e = from_survey(js, json.load(open(p)) if os.path.exists(p) else None)
        e['game'] = a.game
        for k in ('title', 'model', 'outcome', 'family'):
            if getattr(a, k):
                e[k] = getattr(a, k)
        if a.note:
            e['notes'] = (e.get('notes') or []) + a.note
        json.dump(e, open(p, 'w', newline='\n'), indent=1)
        print('kb: wrote docs/kb/games/%s.json (%d routines)' % (a.game, len(e['routines'])))
        print(_line(a.game, e))
    elif a.cmd == 'find':
        ws = [w.lower() for w in a.words]
        for g, e in entries().items():
            if all(w in json.dumps({k: v for k, v in e.items() if k != 'routines'}).lower() or w in g for w in ws):
                print(_line(g, e))
    elif a.cmd == 'match':
        js = json.load(open(os.path.join(a.survey_dir, 'survey.json')))
        hits = match(js.get('routines', []), z80=js.get('inputs', {}).get('z80'))
        for s, mine, game, theirs, role in hits[:20]:
            print('%.2f  %d (0x%04X) ~ %s %d (0x%04X) %s' % (s, mine, mine, game, theirs, theirs, role))
        print('kb: %d match(es) in %d known game(s)' % (len(hits), len(entries())))
    elif a.cmd == 'hw':
        out = hw(a.words)
        print('\n'.join(out[:40]) if out else 'kb: nothing in docs/kb/hardware.json for %s' % ' '.join(a.words))
    elif a.cmd == 'seed':
        done, skipped = seed(a.reference, a.stop, a.only, log=lambda m: print(m, flush=True))
        for k, v in skipped.items():
            print('skipped %s: %s' % (k, v))
        print('kb: seeded %d, skipped %d' % (len(done), len(skipped)))
    else:
        for g, e in entries().items():
            print(_line(g, e))
    return 0


if __name__ == '__main__':
    sys.exit(main())
