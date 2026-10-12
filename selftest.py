#!/usr/bin/env python3
"""nexclash self-test: rebuild the reference games and check every output byte-for-byte.

    python selftest.py [FOLDER] [--human] [--no-repro] [--fast]
    python selftest.py [FOLDER] --smoke      Chuckie Egg only, seconds: the per-change check
    python selftest.py [FOLDER] --tools      the analysis commands (inspect/scan/isr/cost), ~1 min

FOLDER (default: $NEXCLASH_REFERENCE, ./reference or ../specnext/reference - the maintainers'
private reference repo, one subfolder per game; game files are never in the public package) holds the reference inputs under any
names (recognised by MD5; the engine games below also by their canonical name). Runs
`nexclash.py auto` on each snapshot (auto recording, deterministic seed) and
checks the .nex MD5s (default strategy = altrom where proven) and that every
verification and simulated boot PASSED; then rebuilds the old builds with
`--strategy printer|slot1` from the same recordings (REPRO) and checks their
MD5s too (--no-repro skips that). --human also verifies the Fantasy World /
Magicland builds against Dean's own recordings (slower).
Games whose snapshot is missing are skipped and listed. Exit code 0 = all good;
1 = a failure; 2 = no failure but games skipped or outputs not baselined yet
(the new MD5 is printed: paste it into EXPECTED and VERIFICATION.md).
Engine games verified against Dean's recordings (RZX_GAMES: Chuckie Egg, Everyone's a Wally,
Rainbow Islands, Commando) run `auto --no-record --rzx ...` and check both .nex MD5s and the report;
Rainbow Islands takes ~50 min, Commando ~55 min (--fast skips both).
"""
import hashlib, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
INPUTS = {  # md5 -> canonical name
    '7578947fcc8dbc4ba822e2c565499d54': 'treasure_island_dizzy.z80',   # dizzy2_game.z80 (in-game)
    '0659328fd54fd446e39d1740bafd02e7': 'dizzy1.z80',
    '876f474b3441c08ed8ff25bd43d616a3': 'fantasy_world_dizzy.z80',     # the "(a)" keyboard snapshot
    '53078ac60141cd808b609600b85f4094': 'magicland_dizzy.z80',
    '99d9c4c086d06a46ba7a781e5321dc3e': 'dizzy1.rzx',
    '8005fece5a6d6f8792417b592d6b8df1': 'fantasy_world_dizzy.rzx',
    'b4620286854e67b13fb5590476fa17af': 'magicland_dizzy.rzx',
    '703c934aa64c1c1d37d5041dd28cf9c7': 'dizzy5.z80',                  # Dizzy_V.z80 (BASIC loader stage; optional)
    '9443f0cc4c32415849b0419750f1bff3': 'treasure_island_title.z80',   # dizzy2.z80 (title screen; optional)
}
RZX_GAMES = {        # engine games: inputs (canonical name, md5 or None = match by name), outputs
    'chuckie_egg': {'files': [('chuckie_egg.z80', 'cddc0cfea8259d0c497b50fae0acd27e'),
                              ('chuckie_egg.rzx', '7697943d44c33dbef1c073332e36dfc0')],
                    'nex': ('ec0df71e70fae35836eaed521f300777', 'bfad6be1e7c8a2c797a6242d7f339e35')},
    'wally': {'files': [('wally.z80', 'a9eeb555a327e5794b0ba19bc80dccf0'), ('wally.rzx', '72c7d1f6c99407bc21d892d423e89964')], 'alias': {'wallyrzx.rzx': 'wally.rzx'},
              'nex': ('2e615b3e7ae995e6d6a6ed9e3f586d4d', 'f7605489c3af55b8e8c6a580c1c26150')},
    'rainbow': {'files': [('rainbow.z80', '4c98b980b1726af545fccc99665ef29b'), ('rainbow.rzx', '55046d1893bba0a4faf314ecd3a9638b'),
                          ('rainbownew.rzx', '47bb2b163a947724c343a2bc1b039458')],
                'nex': ('7ac543fb51c7a3c4137778eeb3cdc175', 'e50733b2b7e2db32f004c1436a2e0461', '8f25bc6146b9d7f7ae1f12a1d227447e'), 'slow': True},
    'commando': {'files': [('commando.z80', 'c9af5668191462d77c5859900268c24b'),
                           ('commando.rzx', 'b3350a66a14db07add43c878eb872169')],
                 'nex': ('a206f950c12f58a8e7f26b366f5a2480', 'd601385ee4aeb7f3d7c0771bdc27df6b'), 'slow': True},
}
OPTIONAL = {'dizzy5.z80', 'treasure_island_title.z80'}
NO_RECORD = {'treasure_island_title'}   # reference built without a recording (dedicated builder)
EXPECTED = {           # default build (altrom era); None = not baselined yet (needs Dean's reference files)
    'treasure_island_dizzy.nex': '4dae1a3a15b2158642a5d5b82de92ef7',
    'treasure_island_dizzy_sprites.nex': '8b4d0847d68fce3215bd43a0e116e682',
    'dizzy1.nex': '7892b2e0f1f3f9f19165516db307cbe0',
    'dizzy1_sprites.nex': '05d2bce99f4d7654d4e1c9c9c04dc391',
    'fantasy_world_dizzy.nex': 'cd620010e2f61af0002e76718945716f',
    'fantasy_world_dizzy_sprites.nex': '9182f2f8b4b0dc55b59a69728568b403',   # altrom (was printer); baselined 2026-10-11
    'magicland_dizzy.nex': '09eb18496cff334ea17bfc0b0c94585d',
    'magicland_dizzy_sprites.nex': 'bf137d41d3cc08221bf6fdda153c9de2',       # altrom (was slot1); baselined 2026-10-11
    'dizzy5.nex': 'c99189f3274a4803f0b25b0217206bdb',
    'treasure_island_title.nex': '70890aba7d821fba8a41e63636eb58be',
    'treasure_island_title_sprites.nex': '85e054fe4bce8e4b3a8e336aac432f58',   # = dizzy2_title_sprites.nex
    'dizzy5_sprites.nex': '1f33c467e6aa55585cea79cfbb24bcfe',                # altrom (was slot1)
}
REPRO = {              # old builds: game -> (--strategy, sprites .nex MD5)
    'fantasy_world_dizzy': ('printer', 'c09213beaec1572c0228985dae89bd77'),
    'magicland_dizzy': ('slot1', 'd3b37c05d4c47ada07294fa2d7c1ae76'),
    'dizzy5': ('slot1', 'a59c1fd91ec5c32e549526dbc08d2e69'),
}


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def _find(src, want):
    return next((os.path.join(d, f) for d, _, fs in os.walk(src) for f in fs
                 if os.path.getsize(os.path.join(d, f)) < 2_000_000 and md5(os.path.join(d, f)) == want), None)


def tools_check(src):
    """The shared analysis commands (inspect / scan / isr / cost) against facts known from the
    Commando and Chuckie Egg references (~1 min). Returns the number of failures. A session that
    improves a command keeps these passing and adds a check for what it added."""
    import io
    sys.path.insert(0, HERE)
    from nexclash import snapinfo, memscan, isrinfo, drawcost
    cz = _find(src, RZX_GAMES['commando']['files'][0][1])
    cr = _find(src, RZX_GAMES['commando']['files'][1][1])
    ez = _find(src, RZX_GAMES['chuckie_egg']['files'][0][1])
    er = _find(src, RZX_GAMES['chuckie_egg']['files'][1][1]) if len(RZX_GAMES['chuckie_egg']['files']) > 1 else None
    checks = []

    def ok(name, cond, info=''):
        checks.append(cond)
        print('%-4s tools: %s%s' % ('OK' if cond else 'FAIL', name, '' if cond else ' (%s)' % str(info)[:200]))
    old = sys.stderr
    sys.stderr = io.StringIO()                  # SkoolKit's SZX warnings
    try:
        if cz:
            facts, warn = snapinfo.inspect(cz)
            txt = '\n'.join(v for k, v in facts)
            ok('inspect commando: 128K BASIC loader, USR 25088 / 25630',
               '128K' in txt and 'USR targets: 25088' in txt and '25630' in txt
               and any('128K BASIC' in w for w in warn), (txt, warn))
            _, r = memscan.scan(cz, None, 400, '5-14:SPACE; 30-:N', ['0x5C00-0x60FF'], after=25088)
            ok('scan commando start-up (after USR 25088, 400 frames): hook RAM 0x5C00-0x60FF untouched',
               memscan.touched_count(r, '0x5C00-0x60FF') == 0, r['ranges'])
        if cz and cr:
            _, r = memscan.scan(cz, [cr], ranges=['0x5C00-0x60FF'], stop=300)
            ok('scan commando RZX (300 frames): hook RAM untouched', memscan.touched_count(r, '0x5C00-0x60FF') == 0)
            _, r = isrinfo.isr(cz, [cr], stop=200)
            ok('isr commando: reads the interrupted IY (BIT 1,(IY+7) at 29547), not IX',
               29547 in r['reads_entry']['IY'] and not r['reads_entry']['IX'], r['reads_entry'])
            _, r = drawcost.cost(cz, 39120, [cr], stop=1500)
            ok('cost commando plotter 39120 (1500 frames): 2577 calls, median 4477 T',
               r['calls'] == 2577 and r['median'] == 4477, r)
        if ez:
            facts, warn = snapinfo.inspect(ez)
            txt = '\n'.join(v for k, v in facts)
            ok('inspect chuckie: 48K, IM 2, no loader warning', '48K' in txt and 'IM 2' in txt and not warn, (txt, warn))
        if ez and er:
            _, r = isrinfo.isr(ez, [er], stop=150)
            ok('isr chuckie: handler 40092, no IX/IY reads', 40092 in r['entries'] and not any(r['reads_entry'].values()), r)
    finally:
        sys.stderr = old
    if not checks:
        print('tools: reference files not found, nothing checked')
    return checks.count(False)


def smoke(src):
    """--smoke: rebuild the simplest game (Chuckie Egg, stateless alt-ROM hooks) from its snapshot alone
    and compare both .nex MD5s - seconds, catches any shared-code change that alters a build. The full
    selftest (every game + recordings, ~1.5 h) is for releases."""
    spec = RZX_GAMES['chuckie_egg']
    z80 = next((os.path.join(d, f) for d, _, fs in os.walk(src) for f in fs
                if md5(os.path.join(d, f)) == spec['files'][0][1]), None)
    if z80 is None:
        sys.exit('SMOKE: Chuckie Egg snapshot (md5 %s) not found under %s' % (spec['files'][0][1], src))
    work = tempfile.mkdtemp(prefix='nexclash_smoke_')
    shutil.copy(z80, os.path.join(work, 'chuckie_egg.z80'))
    out = os.path.join(work, 'out')
    subprocess.run([sys.executable, os.path.join(HERE, 'nexclash.py'), 'auto', os.path.join(work, 'chuckie_egg.z80'),
                    '-o', out, '--no-record'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    bad = 0
    for suffix, want in zip(('.nex', '_sprites.nex'), spec['nex']):
        p = os.path.join(out, 'chuckie_egg' + suffix)
        got = md5(p) if os.path.exists(p) else None
        bad += got != want
        print('%-4s chuckie_egg%s %s' % ('OK' if got == want else 'FAIL', suffix, got))
    print('SMOKE %s' % ('PASSED' if not bad else 'FAILED'))
    sys.exit(1 if bad else 0)


def main():
    pos = [x for x in sys.argv[1:] if not x.startswith('--')]
    src = pos[0] if pos else next((d for d in (os.environ.get('NEXCLASH_REFERENCE'), os.path.join(HERE, 'reference'),
                                               os.path.join(HERE, '..', 'specnext', 'reference')) if d and os.path.isdir(d)), '')
    if not os.path.isdir(src):
        sys.exit(__doc__)
    if '--smoke' in sys.argv:
        smoke(src)
    if '--tools' in sys.argv:
        bad = tools_check(src)
        print('TOOLS %s' % ('PASSED' if not bad else 'FAILED'))
        sys.exit(1 if bad else 0)
    human, repro, fast = '--human' in sys.argv, '--no-repro' not in sys.argv, '--fast' in sys.argv
    work = tempfile.mkdtemp(prefix='nexclash_selftest_')
    found = {}
    files = [(f, os.path.join(d, f)) for d, _, fs in os.walk(src) for f in fs]   # reference/<game>/...
    for f, p in files:
        if f.lower().endswith('.nex'):
            continue                            # built games kept next to the references
        if os.path.isfile(p) and os.path.getsize(p) < 2_000_000:
            h = md5(p)
            n = INPUTS.get(h)
            for g, spec in RZX_GAMES.items():
                for cn, want in spec['files']:
                    if h == want or (want is None and spec.get('alias', {}).get(f.lower(), f.lower()) == cn):
                        n = cn
            if n:
                shutil.copy(p, os.path.join(work, n))
                found[n] = f
    missing = sorted(set(INPUTS.values()) - set(found) - OPTIONAL)
    if missing:
        print('missing reference files (those games are skipped): %s' % ', '.join(missing))
    fails = pending = 0
    fails += tools_check(src)
    # every hook profile must be exactly what the pinned sjasmplus makes of its asm/ source
    r = subprocess.run([sys.executable, os.path.join(HERE, 'tools', 'asm2profile.py'), '--check', '--all'],
                       capture_output=True, text=True)
    print((r.stdout + r.stderr).strip())
    fails += r.returncode != 0
    print('%-4s hook profiles = pinned sjasmplus output' % ('OK' if r.returncode == 0 else 'FAIL'))
    games = ['fantasy_world_dizzy', 'magicland_dizzy', 'dizzy1', 'treasure_island_dizzy', 'dizzy5', 'treasure_island_title']
    skipped = [g for g in games if g + '.z80' not in found]
    games = [g for g in games if g + '.z80' in found]
    nexclash = os.path.join(HERE, 'nexclash.py')

    def check_report(label, out, g):
        rep = open(os.path.join(out, g + '_report.txt')).read() if os.path.exists(os.path.join(out, g + '_report.txt')) else ''
        if 'FAILED' in rep or 'MISMATCH' in rep or not rep:
            print('FAIL %s verification (see %s)' % (label, out))
            return 1
        print('OK   %s verification (%d PASSED, boot %s)' % (label, rep.count('PASSED'),
              'OK' if 'Boot      : simulated' in rep else 'not simulated'))
        return 0

    for g in games:
        out = os.path.join(work, g + '_out')
        cmd = [sys.executable, nexclash, 'auto', os.path.join(work, g + '.z80'), '-o', out]
        cmd += ['--no-record'] if g in NO_RECORD else []
        extra = []
        if human and g in ('fantasy_world_dizzy', 'magicland_dizzy') and (g + '.rzx') in found:
            extra = ['--rzx', os.path.join(work, g + '.rzx')]
        subprocess.run(cmd + extra, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for suffix in ('.nex', '_sprites.nex'):
            n = g + suffix
            p = os.path.join(out, n)
            got = md5(p) if os.path.exists(p) else None
            if EXPECTED[n] is None and got:
                pending += 1
                print('NEW  %s %s (not baselined: record it in EXPECTED / VERIFICATION.md)' % (n, got))
            else:
                ok = got is not None and got == EXPECTED[n]
                fails += not ok
                print('%-4s %s' % ('OK' if ok else 'FAIL', n))
        fails += check_report(g, out, g)
        if repro and g in REPRO:
            strat, want = REPRO[g]
            ro = os.path.join(work, g + '_' + strat)
            rcmd = [sys.executable, nexclash, 'auto', os.path.join(work, g + '.z80'), '-o', ro, '--no-record',
                    '--rzx', os.path.join(out, g + '_auto.rzx'), '--strategy', strat]
            subprocess.run(rcmd + extra, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            p = os.path.join(ro, g + '_sprites.nex')
            ok = os.path.exists(p) and md5(p) == want
            fails += not ok
            print('%-4s %s_sprites.nex --strategy %s (old build reproduced)' % ('OK' if ok else 'FAIL', g, strat))
            fails += check_report('%s --strategy %s' % (g, strat), ro, g)
    for g, spec in RZX_GAMES.items():
        names = [cn for cn, _ in spec['files']]
        if not all(cn in found for cn in names) or (fast and spec.get('slow')):
            skipped.append(g + (' (--fast)' if fast and spec.get('slow') else ''))
            continue
        out = os.path.join(work, g + '_out')
        cmd = [sys.executable, nexclash, 'auto', os.path.join(work, names[0]), '-o', out, '--no-record']
        for cn in names[1:]:
            cmd += ['--rzx', os.path.join(work, cn)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for cn, _ in spec['files']:
            if dict(spec['files'])[cn] is None:
                print('     %s md5 %s (pin it in RZX_GAMES)' % (cn, md5(os.path.join(work, cn))))
        for suffix, want in zip(('.nex', '_sprites.nex', '_sprites_diag.nex'), spec['nex']):
            p = os.path.join(out, g + suffix)
            ok = os.path.exists(p) and md5(p) == want
            fails += not ok
            print('%-4s %s%s' % ('OK' if ok else 'FAIL', g + suffix, '' if ok else ' (got %s)' % (md5(p) if os.path.exists(p) else 'nothing')))
        fails += check_report(g, out, g)
    if skipped:
        print('SKIPPED (snapshot not supplied): %s' % ', '.join(skipped))
    res = 'FAILED: %d problem(s)' % fails if fails else 'PASSED' if not (skipped or pending) else \
        'PASSED for the games run (%d skipped, %d not baselined)' % (len(skipped), pending)
    print('SELFTEST %s (%s)' % (res, work))
    sys.exit(1 if fails else 2 if (skipped or pending) else 0)


if __name__ == '__main__':
    main()
