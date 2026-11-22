#!/usr/bin/env python3
"""Check the docs against the code and against their size budgets (CLAUDE.md "End of every stage").

    python tools/doccheck.py            exit 0 = PASS, 1 = FAIL (problems listed)

FAIL (in CLAUDE.md, README.md, CONTRIBUTING.md, docs/*.md, .claude/skills/*):
- `python nexclash.py CMD --flag`: CMD or the flag does not exist (each command's --help is read);
- `selftest.py --flag` not in selftest.py's known flags; `python -m nexclash.X` with no module X;
- `module.function(` where module is a toolkit module that has no such top-level name;
- a section reference that resolves to no heading: PLAYBOOK 3c / stage 2, LEARNINGS 2.6,
  BRIEFING C4 / A1, TECHNIQUES 2.6, and BRIEFING C2 #N with no item N (C2 renumbers: check it);
- an engine in nexclash/engines.py without the REQUIRED names of docs/ENGINE_CONTRACT.md;
- technique cards, predicates.json, records' recipes and the generated index (tools/techindex.py);
- the learning loop (tools/learncheck.py, docs/LEARNING.md): lesson dispositions, technique use,
  kept probes, schema-4 cards;
- a file over its size budget (BUDGET below). Why budgets: every session reads these files, and
  without a limit they only grow (LEARNINGS tripled in two weeks). Over budget -> consolidate
  (docs/MAINTAIN.md "Lesson consolidation"), do not raise the number.
WARN only: paths that do not exist (other projects' files and planned files are named on purpose)
and anything in games/*.md (game notes are history; a stale command there misleads one game only).
"""
import ast
import collections
import functools
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# bytes, hand-written ones (lf_size); set 2026-10-26 a little above that day's size: hold the line, lower them as files are condensed
BUDGET = {'docs/ENGINE_CONTRACT.md': 6000, 'CLAUDE.md': 10500, 'docs/PLAYBOOK.md': 27000, 'docs/COLOURS.md': 9000, 'docs/MAINTAIN.md': 6000,
          'docs/BRIEFING.md': 56000, 'docs/LEARNINGS.md': 90000, 'docs/TECHNIQUES.md': 68000,
          'docs/VERIFICATION.md': 72000, 'README.md': 12000, 'docs/techniques/STANDARD.md': 32000,
          'docs/LEARNING.md': 6000, 'tools/probes/README.md': 3000, 'docs/CHECKS.md': 8500}
GAME_BUDGET = 25000          # games/<game>.md; older notes over it are listed and must not grow
GAME_GRANDFATHERED = {'games/rainbow_islands.md': 72000}
SIBLING = ('nexclash/CLAUDE.md', 'nexclash/requirements.txt', 'nexclash/nexclash.py')   # ../nexclash/... in specnext sessions
SKIP_WORDS = {'the', 'and', 'is', 'with', 'or', 'in', 'to', 'only'}


def cli_flags():
    out = {}
    src = open(os.path.join(ROOT, 'nexclash.py')).read()
    help_run = subprocess.run([sys.executable, 'nexclash.py', '--help'], cwd=ROOT, capture_output=True, text=True)
    if help_run.returncode:
        sys.exit('doccheck: cannot inspect nexclash CLI; install requirements.txt with this Python.\n' + help_run.stderr)
    m = re.search(r"\{(auto,patch[^}]*)\}", help_run.stdout)
    cmds = m.group(1).split(',') if m else re.findall(r"add_parser\('(\w+)'", src)
    for c in cmds:
        h = subprocess.run([sys.executable, 'nexclash.py', c, '--help'], cwd=ROOT, capture_output=True, text=True).stdout
        out[c] = set(re.findall(r'(?<![\w-])(--?[a-z][a-z0-9-]*)', h))
    return out


def selftest_flags():
    s = open(os.path.join(ROOT, 'selftest.py')).read()
    m = re.search(r'known = \{([^}]*)\}', s)
    return set(re.findall(r"'(--[a-z-]+)'", m.group(1))) | {'--help'}


@functools.lru_cache(maxsize=None)
def _tree(path):
    """The module's syntax tree, parsed once per run (module_names, engine_contract, auto_contract and copied_pins all
    walk the same files; Codex review P3). Read only: callers never change it."""
    return ast.parse(open(path, encoding='utf-8').read())


@functools.lru_cache(maxsize=None)
def module_names():
    defs = {}
    for p in glob.glob(os.path.join(ROOT, 'nexclash', '*.py')) + glob.glob(os.path.join(ROOT, 'tools', '*.py')):
        try:
            t = _tree(p)
        except SyntaxError:
            continue
        names = set()
        for n in t.body:
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                names.add(n.name)
            elif isinstance(n, ast.Assign):
                names.update(x.id for x in n.targets if isinstance(x, ast.Name))
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                names.update((a.asname or a.name).split('.')[0] for a in n.names)
        defs[os.path.splitext(os.path.basename(p))[0]] = names
    return defs


def headings():
    h = {}
    for d in ('PLAYBOOK', 'LEARNINGS', 'BRIEFING', 'TECHNIQUES'):
        h[d] = [l.strip() for l in open(os.path.join(ROOT, 'docs', d + '.md')) if l.startswith('#')]
    b = open(os.path.join(ROOT, 'docs', 'BRIEFING.md')).read()
    c2 = b[b.index('### C2.'):]
    c2 = c2[:c2.index('\n### ', 5)]
    return h, {int(x) for x in re.findall(r'^(\d+)\. ', c2, re.M)}


CONTRACT = ('auto', 'verify', 'unit_tests', 'load_profile', 'CMP')     # docs/ENGINE_CONTRACT.md REQUIRED


def engine_contract():
    """docs/ENGINE_CONTRACT.md REQUIRED names in every module of nexclash/engines.py (read, not imported)."""
    t = _tree(os.path.join(ROOT, 'nexclash', 'engines.py'))
    table = next(n.value for n in t.body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'ENGINES')
    out = collections.defaultdict(list)
    defs = module_names()                                # once: it parses every module (was once per engine, 90 s)
    for e in table.elts:
        mod, det = e.elts[0].value, e.elts[1].value
        names = defs.get(mod, set())
        miss = [x for x in (det,) + CONTRACT if x not in names]
        if miss:
            out['engine contract: REQUIRED name missing (docs/ENGINE_CONTRACT.md)'].append('nexclash/%s.py  %s' % (mod, ', '.join(miss)))
        if ('RECOLOUR' in names) != ('recolour' in names):
            out['engine contract: RECOLOUR and recolour() go together'].append('nexclash/%s.py' % mod)
    return out


# Engines whose auto() reaches no unit_tests call or no negative-control call (checked by name, one call deep),
# from before the rule (2026-11-22); each comes off when checked or fixed. A new engine is never added here.
AUTO_LEGACY = {'alien_8', 'bruce_lee', 'bubbler', 'chase_hq', 'green_beret', 'head_over_heels', 'highway_encounter',
               'ice_palace', 'ikari_warriors', 'knight_lore', 'lunar_jetman', 'martianoids', 'movie', 'new_zealand_story',
               'pacmania', 'quazatron', 'rainbow', 'rainbow_z80n', 'rainbow_z80n_sky', 'renegade_v12',
               'robin_of_the_wood', 'winter_sports',
               'altered_beast'}   # its negative control runs inside unit_tests ('map negative'): not seen by name


def auto_contract():
    """docs/ENGINE_CONTRACT.md auto(): it runs the unit tests and the negative controls (a call whose name has
    'unit' / 'neg', in auto or one call deep), and an engine replaying through simrun.play_rzx defines on_desync
    (without it a lost sync is a warning and the run passes on the frames before it)."""
    t = _tree(os.path.join(ROOT, 'nexclash', 'engines.py'))
    table = next(n.value for n in t.body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'ENGINES')
    out = collections.defaultdict(list)

    def calls(fn):
        return {getattr(n.func, 'id', None) or getattr(n.func, 'attr', None) or '' for n in ast.walk(fn)
                if isinstance(n, ast.Call)}
    for mod in sorted({e.elts[0].value for e in table.elts}):
        src = open(os.path.join(ROOT, 'nexclash', mod + '.py'), encoding='utf-8').read()
        tree = _tree(os.path.join(ROOT, 'nexclash', mod + '.py'))
        defs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        c = calls(defs['auto']) if 'auto' in defs else set()
        for name in list(c):
            if name in defs and name != 'auto':
                c |= calls(defs[name])
        ok = any('unit' in x.lower() for x in c) and any('neg' in x.lower() for x in c)
        if not ok and mod not in AUTO_LEGACY:
            out['engine contract: auto() must run unit_tests and the negative controls'].append('nexclash/%s.py' % mod)
        if ok and mod in AUTO_LEGACY:
            out['engine contract: AUTO_LEGACY entry now passes, take it off (tools/doccheck.py)'].append(mod)
        if 'play_rzx(' in src and not re.search(r'\bdef on_desync\b|\bon_desync\s*=', src):
            out['engine contract: replays through simrun.play_rzx without on_desync (a lost sync would pass)'].append(
                'nexclash/%s.py' % mod)
    return out


# MD5 literals two engines may share, with why. Any other value in two engine modules is refused: a port
# carries its source's pins along (Stormbringer kept Knight Tyme's loading-screen MD5, 2026-11-22).
SHARED_MD5 = {'cc822d044ec89ffcffbfb3a122f4d088': 'the emu256 256-colour palette table, shared by its sets',
              'b095dc99a047bab844b87b06657b0a7a': 'the same palette file (booty, lode runner v3, lunar jetman, silkworm)',
              '2f0ef98e5c59552663b15d5eb1175236': 'Cauldron and Cauldron 1.1: one game, one recording'}


def copied_pins():
    """Every 32-hex string literal in the engine modules: one owned by two engines (not SHARED_MD5) fails."""
    t = _tree(os.path.join(ROOT, 'nexclash', 'engines.py'))
    table = next(n.value for n in t.body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'ENGINES')
    where = collections.defaultdict(set)
    for mod in sorted({e.elts[0].value for e in table.elts}):
        tree = _tree(os.path.join(ROOT, 'nexclash', mod + '.py'))
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and re.fullmatch(r'[0-9a-f]{32}', n.value):
                where[n.value].add(mod)
    out = collections.defaultdict(list)
    for v, mods in sorted(where.items()):
        if len(mods) > 1 and v not in SHARED_MD5:
            out['engine pins: one MD5 in two engines (a port\'s copied pin? re-derive it, or SHARED_MD5 with why)'].append(
                '%s  %s' % (v, ', '.join(sorted(mods))))
    for v in sorted(set(SHARED_MD5) - {v for v, m in where.items() if len(m) > 1}):
        out['engine pins: SHARED_MD5 entry no longer shared, take it off (tools/doccheck.py)'].append(v)
    return out


def has_section(heads, doc, sec):
    if sec.lower().startswith('stage'):
        pat = re.compile(r'^#+\s*' + re.escape(sec) + r'\b', re.I)
    else:
        pat = re.compile(r'^#+\s*(PART\s+)?' + re.escape(sec) + r'(\b|[.\s:)])', re.I)
    return any(pat.match(x) for x in heads[doc])


GENERATED = re.compile(rb'<!-- generated from docs/records .*?<!-- end generated -->', re.S)   # records.GEN_BEGIN .. GEN_END


def lf_size(f):
    """Bytes as committed (LF): an autocrlf checkout on Windows adds one per line and failed 18 budgets.
    Hand-written bytes only: a list `records views` writes grows a line with every game, and no one can condense it."""
    return len(GENERATED.sub(b'', open(f, 'rb').read().replace(bytes([13, 10]), bytes([10]))))


def main():
    os.chdir(ROOT)
    files = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], capture_output=True,
                           text=True).stdout.split('\0')                # untracked new notes too, NUL-delimited (Codex T6)
    files = [f for f in files if f]
    files = sorted(set(files) | {f.replace(os.sep, '/') for f in glob.glob('docs/*.md')} | {'CLAUDE.md'})   # glob: '\' on Windows listed every doc twice
    docs = [f for f in files if f.endswith('.md') and os.path.exists(f)]
    fl, st, mods = cli_flags(), selftest_flags(), module_names()
    heads, c2 = headings()
    fail, warn = collections.defaultdict(list), collections.defaultdict(list)
    for d in docs:
        sink = warn if d.startswith('games/') else fail
        for i, line in enumerate(open(d), 1):
            loc = '%s:%d' % (d, i)
            for m in re.finditer(r'python3? nexclash\.py\s+([a-z]+)((?:\s+[^`|;)]*)?)', line):
                cmd, rest = m.group(1), m.group(2) or ''
                if cmd not in fl:
                    if cmd not in SKIP_WORDS:
                        sink['unknown nexclash.py command'].append('%s  %s' % (loc, cmd))
                    continue
                for f in re.findall(r'(?<![\w-])(--[a-z][a-z0-9-]*)', rest):
                    if f not in fl[cmd]:
                        sink['unknown flag of nexclash.py ' + cmd].append('%s  %s' % (loc, f))
            for m in re.finditer(r'selftest(?:\.py)?((?:\s+(?:--[a-z-]+|<[^>]+>|[a-z_0-9]+))+)', line):
                for f in re.findall(r'--[a-z][a-z-]*', m.group(1)):
                    if f not in st:
                        sink['unknown selftest.py flag'].append('%s  %s' % (loc, f))
            for m in re.finditer(r'python3? -m nexclash\.([A-Za-z_0-9]+)', line):
                if m.group(1) not in mods:
                    sink['python -m: no such module'].append('%s  %s' % (loc, m.group(1)))
            for m in re.finditer(r'\b([a-z_0-9]+)\.([a-z_][A-Za-z_0-9]*)\(', line):
                mod, fn = m.groups()
                if mod in mods and mod != 'nexclash' and fn not in mods[mod]:
                    sink['module.function not found'].append('%s  %s.%s' % (loc, mod, fn))
            for m in re.finditer(r'\b(PLAYBOOK|LEARNINGS|BRIEFING|TECHNIQUES)\s+((?:[Ss]tage \d)|[A-C]\d+[a-z]?|\d+(?:\.\d+)?[a-z]?)(?:\s+#(\d+))?', line):
                doc, sec, num = m.groups()
                if not has_section(heads, doc, sec):
                    sink['section reference not found'].append('%s  %s %s' % (loc, doc, sec))
                if num and sec == 'C2' and int(num) not in c2:
                    sink['BRIEFING C2 item not found'].append('%s  #%s' % (loc, num))
            for m in re.finditer(r'C2 #(\d+)', line):
                if int(m.group(1)) not in c2:
                    sink['BRIEFING C2 item not found'].append('%s  #%s' % (loc, m.group(1)))
            for m in re.finditer(r'(?<![\w/.])((?:nexclash|docs|asm|games|tools|\.claude|\.github)/[\w./-]+\.(?:py|md|asm|json|yml|txt|bat))', line):
                p = m.group(1).rstrip('.')
                if p.startswith('docs/profiles/') and p.endswith('_colours.json'):
                    continue                    # a game's optional painted-colour file: absent until painted
                if '<' not in p and '*' not in p and p not in SIBLING and not os.path.exists(p):
                    warn['path does not exist'].append('%s  %s' % (loc, p))
    for k, v in engine_contract().items():
        fail[k].extend(v)
    for k, v in auto_contract().items():
        fail[k].extend(v)
    for k, v in copied_pins().items():
        fail[k].extend(v)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from nexclash import records as _records   # assembly a record's sources INCLUDE must be in its data / shared_data
    inc = [b for r in _records.all_records() for b in _records.include_problems(r)]
    if inc:
        fail['record dependencies: assembly INCLUDEs not listed (records.include_problems)'].extend(inc)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import techindex                      # technique cards, predicates, recipes (docs/techniques/STANDARD.md)
    fail['technique cards / recipes (python tools/techindex.py)'].extend(techindex.check())
    if not fail['technique cards / recipes (python tools/techindex.py)']:
        del fail['technique cards / recipes (python tools/techindex.py)']
    import knowledge                      # records' predicate values, docs/risks.json, the export (tools/knowledge.py)
    kb = knowledge.check()
    if kb:
        fail['knowledge data (python tools/knowledge.py check)'].extend(kb)
    import learncheck                     # lessons dispositioned, technique use, probes, new cards (docs/LEARNING.md)
    lb = learncheck.check({'heads': heads, 'c2': c2, 'mods': mods, 'cli': fl, 'has_section': has_section})
    if lb:
        fail['learning loop (python tools/learncheck.py)'].extend(lb)
    for f, cap in BUDGET.items():
        if os.path.exists(f) and lf_size(f) > cap:
            fail['over size budget (consolidate, docs/MAINTAIN.md)'].append('%s  %d > %d bytes' % (f, lf_size(f), cap))
    for f in glob.glob('games/*.md'):
        cap = GAME_GRANDFATHERED.get(f.replace(os.sep, '/'), GAME_BUDGET)    # glob gives '\' on Windows
        if lf_size(f) > cap:
            fail['over size budget (consolidate, docs/MAINTAIN.md)'].append('%s  %d > %d bytes' % (f.replace(os.sep, '/'), lf_size(f), cap))
    for title, d in (('WARN', warn), ('FAIL', fail)):
        for k, v in d.items():
            print('%s %s (%d)' % (title, k, len(v)))
            for x in v[:40]:
                print('     ' + x)
    print('doccheck: %s (%d docs)' % ('FAIL' if fail else 'PASS', len(docs)))
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
