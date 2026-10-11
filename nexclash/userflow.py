"""User-facing commands of the nexclash package (GPL-3.0-or-later).

  patch GAME.z80        build plain + sprite .nex for a supported game (your own snapshot)
  new GAME.z80          unsupported game: make a session folder to add it with Claude
  contribute NAME       zip what a session added (code, profiles, docs, results - never game
                        data) for upload, so everyone gets the game in the next release

Your snapshot never has to match ours byte for byte: every engine checks the ORIGINAL bytes at
each patch site and refuses if they differ. A snapshot identical to one we verified is reported
as VERIFIED (the output .nex MD5s are compared too); any other snapshot of a supported game is
PATCHED (sites checked, not differentially tested against a recording of YOUR snapshot - run
`nexclash.py verify GAME.z80 --rzx YOUR.rzx` for that).
"""
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFIED = os.path.join(ROOT, 'docs', 'profiles', 'verified.json')
CONTRIB = os.path.join(ROOT, 'docs', 'contribute.json')
MANIFEST = os.path.join(ROOT, 'MANIFEST.json')
# what a contribution may contain (package-relative), and what it never may
ALLOWED = ('nexclash/*', 'asm/*', 'docs/*', 'games/*', 'tools/*', 'nexclash.py', 'selftest.py', 'STATUS.md',
           'README.md', 'CLAUDE.md')
GAME_DATA = ('.z80', '.rzx', '.nex', '.sna', '.szx', '.tap', '.tzx', '.dsk', '.scr', '.bin', '.rom', '.pzx',
             '.zip', '.png', '.gif')
MAX_FILE = 512 * 1024


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def verified():
    return json.load(open(VERIFIED)) if os.path.exists(VERIFIED) else {}


# ------------------------------------------------------------------------------------------ patch

def cmd_patch(a, cmd_auto):
    """Build for the user's own snapshot; then say how much of it is proven."""
    z80 = a.z80
    name = os.path.splitext(os.path.basename(z80))[0]
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(z80)), name + '_nexclash')
    h = md5(z80)
    known = verified().get('snapshots', {}).get(h)
    try:
        cmd_auto(a)
    except ValueError as e:                     # an engine's site check refused this snapshot
        print()
        print('Not patched: %s' % e)
        print('This version of the game differs where the patch goes. Start a session to add it:')
        print('    python nexclash.py new %s' % z80)
        return 1
    plain, spr = os.path.join(out, name + '.nex'), os.path.join(out, name + '_sprites.nex')
    rep = open(os.path.join(out, name + '_report.txt')).read() if os.path.exists(
        os.path.join(out, name + '_report.txt')) else ''
    print()
    if not os.path.exists(spr):
        print('No sprite build: this game is not supported yet (plain .nex only: %s).' % (
            'built' if os.path.exists(plain) else 'not built'))
        print('Add it with Claude:  python nexclash.py new %s' % z80)
        return 2
    if 'FAILED' in rep or 'MISMATCH' in rep:
        print('Sprite build FAILED its checks - do not use it. Start a session: python nexclash.py new %s' % z80)
        return 1
    if known:
        want = known.get('nex', {})
        got = {'plain': md5(plain) if os.path.exists(plain) else None, 'sprites': md5(spr)}
        same = all(want.get(k) in (None, got[k]) for k in got)
        print('VERIFIED snapshot: %s (games/%s). Output %s the verified build%s.' % (
            known['game'], known.get('doc', '?'), 'is identical to' if same else 'DIFFERS from',
            '' if same else ' (report this: %s)' % got))
    else:
        print('PATCHED: your snapshot is not byte-identical to the one we verified, but every patch site')
        print('held the original bytes, so the same patch applied. To prove it for YOUR snapshot, record')
        print('an RZX in Fuse (docs/RECORDING_CHECKLIST.md) and run:')
        print('    python nexclash.py verify %s --rzx YOUR.rzx' % z80)
    print('Copy %s to the Next\'s SD card. Hardware checklist: games/ (your game\'s file).' % os.path.basename(spr))
    return 0


# -------------------------------------------------------------------------------------------- new

SESSION = '''# Adding {game} to nexclash - session brief

Made by `nexclash.py new` on {date}. Your snapshot: {z80} (md5 {md5}).
nexclash could not patch it: {why}

## What you need
- This folder, and the nexclash package it came from (or `git clone` of the public repo).
- A recording: open {z80} in Fuse, Options -> RZX: autosave OFF, "Record from snapshot", then play
  3-5 minutes covering what docs/RECORDING_CHECKLIST.md lists. Save it as {game}.rzx in this folder.
- A Claude session that can run code (Claude Code, or claude.ai with code execution).

## Start the session with (copy-paste, attach {z80} and {game}.rzx)
> I want to add a game to nexclash (Spectrum Next colour-clash remover, GPL). The package is
> attached / at <path or repo URL>: follow its CLAUDE.md. Game: {game}. Snapshot and my RZX are
> attached. Which figures should become sprites: <the player / enemies / ...>. Ask me before
> anything that changes what I see.

## When the session is done
1. `python nexclash.py patch {z80}` builds it; test on the Next with the session's checklist.
2. `python nexclash.py contribute {game} --report {game}_nexclash/{game}_report.txt`
   makes nexclash_contribution_{game}.zip: code, profile, notes and results only - no game data.
3. Upload that zip: {upload}
'''


def cmd_new(a, cmd_auto):
    z80 = a.z80
    game = os.path.splitext(os.path.basename(z80))[0]
    folder = a.out or os.path.join(os.path.dirname(os.path.abspath(z80)), game + '_session')
    os.makedirs(folder, exist_ok=True)
    a.out = os.path.join(folder, game + '_nexclash')
    why = 'unknown engine'
    try:
        cmd_auto(a)
        rep = os.path.join(a.out, game + '_report.txt')
        if os.path.exists(rep):
            lines = [x for x in open(rep).read().split('\n') if x.startswith(('Engine', 'Sprites'))]
            why = '; '.join(x.split(':', 1)[1].split('. Add it')[0].strip() for x in lines) or why
    except Exception as e:                      # the plain conversion may still be there
        why = 'nexclash stopped: %s' % e
    c = json.load(open(CONTRIB)) if os.path.exists(CONTRIB) else {}
    upload = c.get('upload_url') or 'see CONTRIBUTING.md in the package'
    open(os.path.join(folder, 'SESSION.md'), 'w').write(SESSION.format(
        game=game, z80=os.path.basename(z80), md5=md5(z80), why=why, upload=upload,
        date=time.strftime('%Y-%m-%d')))
    rc = os.path.join(ROOT, 'docs', 'RECORDING_CHECKLIST.md')
    if os.path.exists(rc):
        open(os.path.join(folder, 'RECORDING_CHECKLIST.md'), 'w').write(open(rc).read())
    print()
    print('Session folder: %s' % folder)
    print('Next: read SESSION.md there (record an RZX, then start a Claude session with its prompt).')
    return 0


# ------------------------------------------------------------------------------------- contribute

def changed_files():
    """Package-relative files added or changed since the release (MANIFEST.json), or, in a git
    checkout without a manifest, since the last commit (uncommitted + untracked)."""
    if os.path.exists(MANIFEST):
        base = json.load(open(MANIFEST))['files']
        out = []
        for d, _, fs in os.walk(ROOT):
            if '.git' in d.split(os.sep) or '__pycache__' in d:
                continue
            for f in fs:
                rel = os.path.relpath(os.path.join(d, f), ROOT).replace(os.sep, '/')
                if rel == 'MANIFEST.json':
                    continue
                if base.get(rel) != md5(os.path.join(ROOT, rel)):
                    out.append(rel)
        return sorted(out)
    if os.path.isdir(os.path.join(ROOT, '.git')):
        r = subprocess.run(['git', '-C', ROOT, 'status', '--porcelain', '-uall'], capture_output=True, text=True)
        return sorted(l[3:].strip().strip('"') for l in r.stdout.splitlines() if not l.startswith(' D'))
    sys.exit('No MANIFEST.json and not a git checkout: cannot tell what the session changed.')


def screen(files):
    """(kept, refused-with-reason)."""
    keep, refused = [], []
    for f in files:
        p = os.path.join(ROOT, f)
        if f.lower().endswith(GAME_DATA):
            refused.append((f, 'game data or binary (never uploaded)'))
        elif not any(fnmatch.fnmatch(f, g) for g in ALLOWED):
            refused.append((f, 'outside the toolkit folders'))
        elif os.path.isfile(p) and os.path.getsize(p) > MAX_FILE:
            refused.append((f, 'larger than %d KB' % (MAX_FILE // 1024)))
        elif os.path.isfile(p):
            keep.append(f)
    return keep, refused


def cmd_contribute(a):
    files = changed_files()
    keep, refused = screen(files)
    for f, why in refused:
        print('left out: %s (%s)' % (f, why))
    if not keep:
        print('Nothing to contribute: no toolkit file was added or changed.')
        return 1
    zname = os.path.abspath(a.output or 'nexclash_contribution_%s.zip' % a.name)
    meta = {'game': a.name, 'date': time.strftime('%Y-%m-%d'), 'note': a.note or '',
            'package_version': open(os.path.join(ROOT, 'VERSION')).read().strip()
            if os.path.exists(os.path.join(ROOT, 'VERSION')) else 'git',
            'files': {f: md5(os.path.join(ROOT, f)) for f in keep}, 'reports': []}
    with zipfile.ZipFile(zname, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in keep:
            z.write(os.path.join(ROOT, f), 'files/' + f)
        for r in a.report or []:                 # nexclash reports: text, results and MD5s only
            if os.path.getsize(r) <= MAX_FILE and not r.lower().endswith(GAME_DATA):
                z.write(r, 'reports/' + os.path.basename(r))
                meta['reports'].append(os.path.basename(r))
        z.writestr('CONTRIBUTION.json', json.dumps(meta, indent=1))
    c = json.load(open(CONTRIB)) if os.path.exists(CONTRIB) else {}
    print('Contribution: %s (%d files%s)' % (zname, len(keep), ', %d reports' % len(meta['reports'])
                                             if meta['reports'] else ''))
    for f in keep:
        print('  ' + f)
    print('Upload it: %s' % (c.get('upload_url') or 'see CONTRIBUTING.md'))
    if c.get('pull_requests'):
        print('(GitHub users can open a pull request instead: %s)' % c['pull_requests'])
    return 0
