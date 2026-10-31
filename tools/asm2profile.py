"""Assemble an engine's hook source and write (or check) the hook hex in its profile.

    python tools/asm2profile.py commando              reassemble, update docs/profiles/commando.json
    python tools/asm2profile.py --check --all         reassemble every engine, compare, write nothing
    python tools/asm2profile.py commando --add-sym show.lk   also export that symbol

Works for every profile with a "hooks" section that names its source ("source": asm/<x>.asm):
- the pinned sjasmplus (tools/sjasmplus/pin.json) assembles it with --zxnext in a temp dir;
- every SAVEBIN "<prefix>_<key>.bin" output becomes hooks[<key>] (hex, in the case the profile
  already uses; new blocks upper-case);
- hooks["syms"] keeps its own key set (plus --add-sym) and is refreshed from the symbol file,
  in the profile's existing format ("0x3600" or "3600");
- hooks["assembled_with"] records the assembler version.
Nothing else in the profile is touched. --check exits 1 on any difference (bytes, sizes,
symbols, a missing/extra block) - the test for an assembler upgrade and for a stale profile.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'sjasmplus'))
import sjasm  # noqa: E402

PROFILES = os.path.join(ROOT, 'docs', 'profiles')
SAVEBIN = re.compile(r'^\s*SAVEBIN\s+"([^"]+)"', re.M | re.I)
SYM = re.compile(r'^([A-Za-z_][\w.]*):\s+EQU\s+0x([0-9A-Fa-f]+)')


def hook_profiles():
    out = []
    for p in sorted(glob.glob(os.path.join(PROFILES, '*.json'))):
        try:
            d = json.load(open(p))
        except ValueError:
            continue
        if isinstance(d, dict) and isinstance(d.get('hooks'), dict) and d['hooks'].get('source'):
            out.append(os.path.splitext(os.path.basename(p))[0])
    return out


def assemble(src, exe):
    """-> ({key: bytes}, {symbol: value}). Key = SAVEBIN file name minus '<prefix>_' and '.bin'."""
    text = open(src).read()
    names = SAVEBIN.findall(text)
    if not names:
        raise RuntimeError('%s has no SAVEBIN' % src)
    with tempfile.TemporaryDirectory() as tmp:
        # forward slashes: sjasmplus warns on '\' in a file name (Windows paths; 2026-10-31)
        r = subprocess.run([exe, '--zxnext', '--msg=war', '--sym=hooks.sym', src.replace('\\', '/')], cwd=tmp,
                           capture_output=True, text=True)
        msg = r.stdout + r.stderr
        if r.returncode or 'error' in msg.lower() or 'warning' in msg.lower():
            raise RuntimeError('sjasmplus %s:\n%s' % (src, msg.strip()))
        blocks = {}
        for n in names:
            base = os.path.splitext(os.path.basename(n))[0]
            key = base.split('_', 1)[1] if '_' in base else base
            if key in blocks:
                raise RuntimeError('%s: two SAVEBIN outputs map to key %r' % (src, key))
            blocks[key] = open(os.path.join(tmp, n), 'rb').read()
        syms = {}
        for line in open(os.path.join(tmp, 'hooks.sym')):
            m = SYM.match(line)
            if m:
                syms[m.group(1)] = int(m.group(2), 16)
    return blocks, syms


def run(name, exe, check, add_syms=()):
    path = os.path.join(PROFILES, name + '.json')
    text = open(path).read()
    prof = json.loads(text)
    h = prof['hooks']
    src = os.path.join(ROOT, h['source'])
    blocks, syms = assemble(src, exe)
    problems = []
    for key, data in blocks.items():
        old = h.get(key)
        new = data.hex() if old and old == old.lower() and old != old.upper() else data.hex().upper()
        if old is None:
            problems.append('new block %s (%d bytes)' % (key, len(data)))
        elif old.lower() != new.lower():
            problems.append('block %s differs (%d -> %d bytes)' % (key, len(old) // 2, len(data)))
        h[key] = new
    for key in sorted(k for k in h if k not in blocks and k not in ('source', 'syms', 'assembled_with')
                      and isinstance(h[k], str) and re.fullmatch(r'[0-9A-Fa-f]*', h[k] or 'x')):
        problems.append('profile block %s has no SAVEBIN in the source' % key)
    old_syms = h.get('syms', {})
    fmt = '0x%04X' if any(str(v).lower().startswith('0x') for v in old_syms.values()) or not old_syms \
        else '%04X'
    new_syms = {}
    for k in sorted(set(old_syms) | set(add_syms)):
        if k not in syms:
            problems.append('symbol %s not in the source' % k)
            continue
        new_syms[k] = fmt % syms[k]
        if k in old_syms and int(str(old_syms[k]), 16) != syms[k]:
            problems.append('symbol %s %s -> %s' % (k, old_syms[k], new_syms[k]))
        elif k not in old_syms:
            problems.append('new symbol %s = %s' % (k, new_syms[k]))
    h['syms'] = new_syms
    ver = 'sjasmplus ' + sjasm.PIN['version']
    if h.get('assembled_with') != ver:
        if not check:
            problems.append('assembled_with %s -> %s' % (h.get('assembled_with'), ver))
        h['assembled_with'] = ver
    if check:
        real = [p for p in problems if not p.startswith('assembled_with')]
        print('%-22s %s' % (name, 'IDENTICAL (%d blocks, %d symbols)' % (len(blocks), len(new_syms))
                             if not real else 'DIFFERS: ' + '; '.join(real)))
        return not real
    out = json.dumps(prof, indent=1)
    if out != text:
        open(path, 'w').write(out)
    print('%-22s %s' % (name, 'written: ' + '; '.join(problems) if problems else 'unchanged'))
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('names', nargs='*', help='profile names (docs/profiles/<name>.json)')
    ap.add_argument('--all', action='store_true', help='every profile with hooks.source')
    ap.add_argument('--check', action='store_true', help='compare only; exit 1 on a difference')
    ap.add_argument('--add-sym', action='append', default=[], help='export this symbol too')
    a = ap.parse_args(argv)
    names = hook_profiles() if a.all else a.names
    if not names:
        ap.error('name a profile or use --all (profiles with hooks: %s)' % ', '.join(hook_profiles()))
    exe = sjasm.find()
    ok = all([run(n, exe, a.check, a.add_sym) for n in names])
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
