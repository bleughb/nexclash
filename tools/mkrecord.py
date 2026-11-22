"""mkrecord.py SPEC.json REFERENCE_DIR [--stamp]: write a new game's evidence record in one go.

Stages the inputs into REFERENCE_DIR/<name>/ (copied, MD5s taken from the copies), writes docs/records/<name>.json with
the outputs a real rebuild gives, adds the techniques / results / feasibility blocks doccheck asks for, gives
games/<doc> its `Techniques:` line and a `## Friction` skeleton when it has none, regenerates the views; --stamp then
runs `selftest.py --game <name> --verify --stamp`. Fill the Friction lines and the feasibility evidence before the PR.

SPEC (JSON):
  name, order, game, doc, engine        record identity (order: the next free number, see docs/records)
  snapshot: [path, note]                the .z80 the record builds from
  recordings: [[path, staged name, role], ...]
  pok: [path, note]                     optional: the checked cheats
  outputs: {kind: file}                 e.g. {"plain": "<name>.nex", "sprites": "<name>_sprites.nex"}
  data: [...], shared_data: [...]       files the build reads (profile, asm; asm/lib files used)
  minutes, verify_note                  verify cost and what auto checks
  status: {title, engine_col, build, software, hardware, next}
  techniques: [[application, card id, revision, target], ...]
  result: {application, check, scope, evidence}       the main result (build = the sprite output's MD5)
  feasibility: {pacing, dependencies, decision, next_experiment}   (tools/templates/feasibility.json)
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def stage(spec, ref):
    n = spec['name']
    d = os.path.join(ref, n)
    os.makedirs(d, exist_ok=True)
    shutil.copy(spec['snapshot'][0], os.path.join(d, n + '.z80'))
    snap = {'name': n + '.z80', 'md5': md5(os.path.join(d, n + '.z80')), 'path': '%s/%s.z80' % (n, n),
            'note': spec['snapshot'][1]}
    recs = []
    for src, name, role in spec.get('recordings', []):
        shutil.copy(src, os.path.join(d, name))
        recs.append({'name': name, 'md5': md5(os.path.join(d, name)), 'path': '%s/%s' % (n, name), 'role': role})
    if spec.get('pok'):
        shutil.copy(spec['pok'][0], os.path.join(d, n + '.pok'))
        recs.append({'name': n + '.pok', 'md5': md5(os.path.join(d, n + '.pok')), 'path': '%s/%s.pok' % (n, n),
                     'note': spec['pok'][1]})
    return snap, recs


def record(spec, snap, recs):
    return {'name': spec['name'], 'order': spec['order'], 'game': spec['game'], 'doc': spec['doc'],
            'engine': spec['engine'], 'representative': True, 'reference': spec['name'],
            'inputs': {'snapshot': snap, 'recordings': recs},
            'modules': [spec['engine']], 'own_modules': [spec['engine']],
            'data': spec['data'], 'shared_data': spec.get('shared_data', []),
            'rebuild': {'args': ['--no-record'], 'rzx': [], 'decisions': None},
            'verify': {'args': ['--no-record'], 'rzx': [r[1] for r in spec.get('recordings', [])], 'auto_record': False,
                       'minutes': spec['minutes'], 'note': spec['verify_note']},
            'outputs': {k: {'file': f, 'md5': '0' * 32} for k, f in spec['outputs'].items()},
            'repro': [], 'status': spec['status'], 'checks': ['asm2profile:' + spec.get('profile', spec['engine'])],
            'techniques': [{'application': a, 'id': i, 'revision': v, 'target': t, 'phases': []}
                           for a, i, v, t in spec.get('techniques', [])],
            'feasibility': spec['feasibility']}


def notes(spec):
    """games/<doc>: the Techniques line (doccheck) and a Friction skeleton (learncheck), when missing."""
    p = os.path.join(ROOT, 'games', spec['doc'])
    if not os.path.exists(p):
        return
    t = open(p, encoding='utf-8').read()
    ids = ', '.join('`%s`' % x[1] for x in spec.get('techniques', []))
    if ids and not re.search(r'^Techniques: ', t, re.M):
        t = t.replace('\n## ', '\nTechniques: %s\n\n## ' % ids, 1)
    if '## Friction' not in t:
        t = t.rstrip('\n') + ('\n\n## Friction\n- reuse: [local: FILL IN]\n- retries: [local: FILL IN]\n'
                              '- environment: [local: FILL IN]\n- hand-rolled: [none: FILL IN]\n- scratch: [none: FILL IN]\n')
    open(p, 'w', encoding='utf-8').write(t)


def main(argv):
    spec = json.load(open(argv[0]))
    ref = os.path.abspath(argv[1])
    py = sys.executable
    snap, recs = stage(spec, ref)
    rec = record(spec, snap, recs)
    p = os.path.join(ROOT, 'docs', 'records', spec['name'] + '.json')
    json.dump(rec, open(p, 'w'), indent=1)
    subprocess.run([py, '-m', 'nexclash.records', 'views'], cwd=ROOT, capture_output=True, text=True)
    out = subprocess.run([py, 'selftest.py', ref, '--game', spec['name']], cwd=ROOT, capture_output=True,
                         text=True).stdout       # the caller's environment: selftest's own access rules apply
    seeded = re.compile(r'FAIL %s rebuild (\S+) \(got ([0-9a-f]{32})\)' % re.escape(spec['name']))
    got = dict(seeded.findall(out))
    other = [l for l in out.splitlines() if l.startswith('FAIL') and not seeded.match(l)]
    missing = [f for f in spec['outputs'].values() if f not in got]
    if other or missing:                         # only the seeded checksum mismatches are expected: a build,
        sys.exit('the rebuild failed (no record written past the inputs):\n%s%s' % (   # boot or NEXLOAD failure stops here
            '\n'.join(other)[:3000], '\nno output for %s' % missing if missing else ''))
    for k, f in spec['outputs'].items():
        rec['outputs'][k]['md5'] = got[f]
    if spec.get('result'):
        sprites = rec['outputs'].get('sprites', next(iter(rec['outputs'].values())))['md5'][:8]
        rec['results'] = [dict(spec['result'], status='pass', build=sprites)]
    json.dump(rec, open(p, 'w'), indent=1)
    notes(spec)
    subprocess.run([py, '-m', 'nexclash.records', 'views'], cwd=ROOT, capture_output=True, text=True)
    print('wrote %s; outputs %s' % (os.path.relpath(p, ROOT), {k: v['md5'][:8] for k, v in rec['outputs'].items()}))
    if '--stamp' in argv:
        r = subprocess.run([py, 'selftest.py', ref, '--game', spec['name'], '--verify', '--stamp'], cwd=ROOT,
                           capture_output=True, text=True)
        keep = ('FAIL', 'stamped', 'SELFTEST', 'INCOMPLETE', 'SKIPPED', 'WARNING')
        print('\n'.join(l for l in r.stdout.splitlines() if l.startswith(keep)))
        if r.returncode:                         # 2 = incomplete (a game skipped, nothing stamped): not a verification
            print('selftest exited %d: the record is NOT verified' % r.returncode)
        return r.returncode
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
