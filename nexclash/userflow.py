"""User-facing commands of the nexclash package (GPL-3.0-or-later).

  patch GAME.z80        build a supported game (your own snapshot): GAME.nxc, the file to share
                        (it needs the player's own game; --nex keeps the plain + sprite .nex too)
  new GAME.z80          unsupported game: make a session folder to add it with Claude
  contribute NAME       zip what a session added (code, profiles, docs, results, the game's .nxc -
                        never game data) for upload, so everyone gets the game in the next release

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
ALLOWED = ('nexclash/*', 'asm/*', 'docs/*', 'games/*', 'tools/*', '.github/*', '.claude/*',
           'nexclash.py', 'selftest.py', 'STATUS.md', 'README.md', 'CLAUDE.md', 'CONTRIBUTING.md',
           'requirements.txt', 'VERSION', 'LICENSE', 'THIRD-PARTY-NOTICES', '.gitignore')
GAME_DATA = ('.z80', '.rzx', '.nex', '.sna', '.szx', '.tap', '.tzx', '.dsk', '.scr', '.bin', '.rom', '.pzx',
             '.zip', '.png', '.gif')
CACHE_DIRS = ('.git', '__pycache__', '.venv', '.tox', '.nox', '.pytest_cache', '.mypy_cache', '.ruff_cache')
GENERATED_ROOTS = ('venv', 'env', 'node_modules', 'dist', 'build', 'htmlcov', 'contrib_reports',
                   '*_nexclash', '*_out', '*_session', '*_survey', 'out_*', '.recolour_*')
GENERATED_FILES = ('*.pyc', '*.pyo', '*.log', '.coverage')
DISCOVERY_EXCLUDES = tuple(x + '/' for x in CACHE_DIRS) + tuple('/' + x + '/' for x in GENERATED_ROOTS) + GENERATED_FILES


MAX_FILE = 512 * 1024
MAX_NXC = 4 * 1024 * 1024        # a .nxc: the patch to share (encrypted with the game; no game data in clear)


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def verified():
    return json.load(open(VERIFIED)) if os.path.exists(VERIFIED) else {}


# ------------------------------------------------------------------------------------------ patch

def artifact_state(path):
    """Distinguish this run's writes, including byte-identical rebuilds, from old outputs."""
    try:
        st = os.stat(path)
        return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns
    except FileNotFoundError:
        return None


def cmd_patch(a, cmd_auto):
    """Build for the user's own snapshot; then say how much of it is proven."""
    z80 = a.z80
    name = os.path.splitext(os.path.basename(z80))[0]
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(z80)), name + '_nexclash')
    h = md5(z80)
    known = verified().get('snapshots', {}).get(h)
    plain, spr = os.path.join(out, name + '.nex'), os.path.join(out, name + '_sprites.nex')
    previous = artifact_state(spr)
    try:
        if cmd_auto(a) is False:
            print('Sprite build FAILED its checks; previous output files are not a new build.')
            return 1
    except ValueError as e:                     # an engine's site check refused this snapshot
        print()
        print('Not patched: %s' % e)
        print('This version of the game differs where the patch goes. Start a session to add it:')
        print('    python nexclash.py new %s' % z80)
        return 1
    rep = open(os.path.join(out, name + '_report.txt')).read() if os.path.exists(
        os.path.join(out, name + '_report.txt')) else ''
    print()
    current = artifact_state(spr)
    if current is not None and current == previous:
        print('No sprite build from this run: %s is an earlier output, kept unchanged. Do not use it as this run\'s result.' % spr)
        return 2
    if current is None:
        print('No sprite build: this game is not supported yet (plain .nex only: %s).' % (
            'built' if os.path.exists(plain) else 'not built'))
        print('Add it with Claude:  python nexclash.py new %s' % z80)
        return 2
    if 'FAILED' in rep or 'MISMATCH' in rep:
        print('Sprite build FAILED its checks - do not use it. Start a session: python nexclash.py new %s' % z80)
        return 1
    if known and getattr(a, 'allow_60hz', False):
        print('Recognised snapshot: %s (games/%s); --allow-60hz output has not been compared to the reference.' % (known['game'], known.get('doc', '?')))
    elif known:
        want = known.get('nex', {})
        got = {'plain': md5(plain) if os.path.exists(plain) else None, 'sprites': md5(spr)}
        same = all(want.get(k) is not None and want[k] == got[k] for k in got)
        print('Recognised snapshot: %s (games/%s). Output %s the reference build%s.' % (
            known['game'], known.get('doc', '?'), 'is identical to' if same else 'DIFFERS from',
            '' if same else ' (report this: %s)' % got))
    else:
        print('PATCHED: your snapshot is not byte-identical to the one we verified, but every patch site')
        print('held the original bytes, so the same patch applied. To prove it for YOUR snapshot, record')
        print('an RZX in Fuse (docs/RECORDING_CHECKLIST.md) and run:')
        print('    python nexclash.py verify %s --rzx YOUR.rzx' % z80)
    if known and not getattr(a, 'allow_60hz', False) and not same:
        return 1
    from nexclash import nxcout                 # GAME.nxc (nexclash/nxcout.py); the .nex files only with --nex
    nxc = nxcout.package(a)
    print('Share %s; to play it, the loader and card setup: %s. Hardware checklist: games/ (your game\'s file).' % (
        os.path.basename(nxc), nxcout.SHARE) if nxc else 'Copy %s to the Next\'s SD card. Hardware checklist: games/ '
        '(your game\'s file).' % os.path.basename(spr))
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
> attached. Show me the preview and the design defaults (PLAYBOOK 3c) and ask me before anything
> that changes what I see.

Work goes in stages (PLAYBOOK "Sessions"). Preserve a handoff at each stage; start a new chat at
a meaningful boundary when context is large or the environment changes, e.g.
> Continue {game} in nexclash (package attached / at <path>): follow its CLAUDE.md, start from the
> "Next session" block in games/<game>.md.
Reply to the design question with "defaults" or the numbers to change.
Git: retain branch and commit; follow docs/LEARNING.md before final verification.
Release zip: retain the whole modified package and MANIFEST.json; do not run Git refresh/commit.

## When the session is done
1. `python nexclash.py patch "{z80path}"` builds {game}.nxc (add `--nex` for the .nex files to test on
   the Next with the session's checklist; the .nxc loader: github.com/jattree/nxc).
2. `python nexclash.py contribute "{game}" --report "{report}"`
   makes nexclash_contribution_{game}.zip: code, profile, notes, results and {game}.nxc - no game data.
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
        from nexclash import nxcout             # a game an engine already builds still gets its .nxc
        nxcout.package(a)
        rep = os.path.join(a.out, game + '_report.txt')
        if os.path.exists(rep):
            lines = [x for x in open(rep).read().split('\n') if x.startswith(('Engine', 'Sprites'))]
            parts = [x.split(':', 1)[1].split('. Add it')[0].strip() for x in lines]
            why = '; '.join(p_ for p_ in parts if p_ != 'unknown') or why          # 'unknown' engine: said by the Sprites line
    except Exception as e:                      # the plain conversion may still be there
        why = 'nexclash stopped: %s' % e
    c = json.load(open(CONTRIB)) if os.path.exists(CONTRIB) else {}
    upload = c.get('upload_url') or 'see CONTRIBUTING.md in the package'
    open(os.path.join(folder, 'SESSION.md'), 'w').write(SESSION.format(
        game=game, z80=os.path.basename(z80), z80path=os.path.abspath(z80),
        report=os.path.join(os.path.dirname(os.path.abspath(z80)), game + '_nexclash', game + '_report.txt'),
        md5=md5(z80), why=why, upload=upload,
        date=time.strftime('%Y-%m-%d')))
    rc = os.path.join(ROOT, 'docs', 'RECORDING_CHECKLIST.md')
    if os.path.exists(rc):
        open(os.path.join(folder, 'RECORDING_CHECKLIST.md'), 'w').write(open(rc).read())
    print()
    print('Session folder: %s' % folder)
    print('Next: read SESSION.md there (record an RZX, then start a Claude session with its prompt).')
    return 0


# ------------------------------------------------------------------------------------- contribute

def generated_path(relative, directory=False):
    """Generated files are excluded from discovery; tracked/manifest changes are still checked."""
    parts = relative.split('/')
    directories = parts if directory else parts[:-1]
    return (any(p in CACHE_DIRS for p in directories)
            or bool(directories and any(fnmatch.fnmatch(parts[0], g) for g in GENERATED_ROOTS))
            or (not directory and any(fnmatch.fnmatch(parts[-1], g) for g in GENERATED_FILES)))


def resolve_git_base(base_ref=None):
    """A reviewed ancestor of HEAD, never a stale starting point that re-exports merged upstream work."""
    def git(*args):
        return subprocess.run(['git', '-C', ROOT, *args], capture_output=True, text=True)
    default = git('merge-base', 'HEAD', 'origin/main')
    if base_ref is None and default.returncode:
        sys.exit('Cannot find origin/main merge base; fetch main or provide a reviewed ancestor with --base.')
    chosen = git('rev-parse', '--verify', (base_ref or default.stdout.strip()) + '^{commit}')
    if chosen.returncode:
        sys.exit('Invalid contribution baseline: ' + (base_ref or 'origin/main'))
    base = chosen.stdout.strip()
    if git('merge-base', '--is-ancestor', base, 'HEAD').returncode:
        sys.exit('Contribution --base must be an ancestor of HEAD.')
    current = default.stdout.strip()
    if base_ref and not default.returncode and base != current and git('merge-base', '--is-ancestor', current, base).returncode:
        sys.exit('--base does not include the current merge base and would include upstream changes; omit --base after refreshing main.')
    return base


def changed_files(base_ref=None):
    """Committed/uncommitted toolkit work, with generated directories pruned before discovery/hashing."""
    if os.path.exists(MANIFEST):
        if base_ref:
            sys.exit('--base applies only to Git checkouts; release packages use their original manifest.')
        base = json.load(open(MANIFEST))['files']
        deleted = [f for f in base if not os.path.isfile(os.path.join(ROOT, f))]
        if deleted:
            sys.exit('Contribution contains deletions (including renames); submit a pull request: ' + ', '.join(deleted))
        # Always inspect original files, even if they now match an ignore pattern.
        out = {f for f, h in base.items() if md5(os.path.join(ROOT, f)) != h}
        for d, dirs, fs in os.walk(ROOT):
            relative = os.path.relpath(d, ROOT).replace(os.sep, '/')
            prefix = '' if relative == '.' else relative + '/'
            dirs[:] = [x for x in dirs if not generated_path(prefix + x, directory=True)]
            for f in fs:
                rel = prefix + f
                if rel not in base and rel != 'MANIFEST.json' and not generated_path(rel):
                    out.add(rel)  # New files need no hash until they pass the export policy.
        return sorted(out)
    if os.path.exists(os.path.join(ROOT, '.git')):
        def git(*args):
            result = subprocess.run(['git', '-C', ROOT, *args], capture_output=True, text=True)
            if result.returncode:
                sys.exit('Cannot determine contribution changes: ' + result.stderr.strip())
            return result.stdout
        base = resolve_git_base(base_ref)
        changed = git('diff', '--name-only', '-z', '--no-renames', base).split('\0')
        untracked = git('ls-files', '--others', '--exclude-standard', '-z',
                        *['--exclude=' + g for g in DISCOVERY_EXCLUDES]).split('\0')
        files = sorted(set(filter(None, changed + untracked)))
        deleted = [f for f in files if not os.path.isfile(os.path.join(ROOT, f))]
        if deleted:
            sys.exit('Contribution contains deletions (including renames); submit a pull request: ' + ', '.join(deleted))
        print('Contribution baseline: ' + base)
        return files
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


def contribution_base(files, base_ref=None):
    """Original hashes let the importer refuse replacements of newer maintainer files."""
    if os.path.exists(MANIFEST):
        manifest = json.load(open(MANIFEST))
        return ({'kind': 'package', 'version': manifest.get('version'), 'manifest_md5': md5(MANIFEST)},
                {f: manifest['files'].get(f) for f in files})
    def git(*args):
        return subprocess.run(['git', '-C', ROOT, *args], capture_output=True)
    base = resolve_git_base(base_ref)
    originals = {}
    for f in files:
        result = git('show', base + ':' + f)
        originals[f] = hashlib.md5(result.stdout).hexdigest() if not result.returncode else None
    return {'kind': 'git', 'commit': base}, originals


def cmd_contribute(a):
    files = changed_files(getattr(a, 'base', None))
    excluded = sorted(set(getattr(a, 'exclude', None) or []))
    if set(excluded) - set(files):
        sys.exit('--exclude does not name changed files: ' + ', '.join(sorted(set(excluded) - set(files))))
    files = [f for f in files if f not in excluded]
    keep, refused = screen(files)
    # Player inputs outside toolkit paths are expected; unsupported source changes require a decision.
    data = [f for f, _ in refused if f.lower().endswith(GAME_DATA) and not f.startswith('assets/')
            and not any(fnmatch.fnmatch(f, g) for g in ALLOWED)]
    blocked = [(f, why) for f, why in refused if f not in data]
    if data:
        print('Excluded %d game-data/binary file(s); these are never exported.' % len(data))
    for f in excluded:
        print('Explicitly excluded: ' + f)
    if blocked:
        for f, why in blocked[:10]:
            print('Cannot include: %s (%s)' % (f, why))
        if len(blocked) > 10:
            print('... %d more unsupported changes' % (len(blocked) - 10))
        print('No archive written: move unrelated files out, explicitly --exclude them, or use a PR for required unsupported files.')
        return 1
    if not keep:
        print('Nothing to contribute: no toolkit file was added or changed.')
        return 1
    source, originals = contribution_base(keep, getattr(a, 'base', None))
    zname = os.path.abspath(a.output or 'nexclash_contribution_%s.zip' % a.name)
    meta = {'schema': 2, 'source': source, 'base_files': originals, 'excluded': excluded, 'game': a.name, 'date': time.strftime('%Y-%m-%d'), 'note': a.note or '',
            'package_version': open(os.path.join(ROOT, 'VERSION')).read().strip()
            if os.path.exists(os.path.join(ROOT, 'VERSION')) else 'git',
            'files': {f: md5(os.path.join(ROOT, f)) for f in keep}, 'reports': [], 'patches': {}}
    with zipfile.ZipFile(zname, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in keep:
            z.write(os.path.join(ROOT, f), 'files/' + f)
        for r in a.report or []:                 # nexclash reports: text, results and MD5s only
            if os.path.getsize(r) <= MAX_FILE and not r.lower().endswith(GAME_DATA):
                z.write(r, 'reports/' + os.path.basename(r))
                meta['reports'].append(os.path.basename(r))
            if r.endswith('_report.txt'):           # the build's .nxc beside its report (nexclash/nxcout.py), never the .nex
                nxc = r[:-len('_report.txt')] + '.nxc'
                if os.path.isfile(nxc) and os.path.getsize(nxc) <= MAX_NXC:
                    z.write(nxc, 'patches/' + os.path.basename(nxc))
                    meta['patches'][os.path.basename(nxc)] = md5(nxc)
        z.writestr('CONTRIBUTION.json', json.dumps(meta, indent=1))
    c = json.load(open(CONTRIB)) if os.path.exists(CONTRIB) else {}
    print('Contribution: %s (%d files%s%s)' % (zname, len(keep), ', %d reports' % len(meta['reports'])
                                               if meta['reports'] else '', ', %s' % ', '.join(meta['patches'])
                                               if meta['patches'] else ''))
    for f in keep:
        print('  ' + f)
    print('Upload it: %s' % (c.get('upload_url') or 'see CONTRIBUTING.md'))
    if c.get('pull_requests'):
        print('(GitHub users can open a pull request instead: %s)' % c['pull_requests'])
    return 0
