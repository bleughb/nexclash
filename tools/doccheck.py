#!/usr/bin/env python3
"""Check the docs against the code and against their size budgets (CLAUDE.md "End of every stage").

    python tools/doccheck.py            exit 0 = PASS, 1 = FAIL (problems listed)

FAIL (in CLAUDE.md, README.md, CONTRIBUTING.md, docs/*.md, .claude/skills/*):
- `python nexclash.py CMD --flag`: CMD or the flag does not exist (each command's --help is read);
- `selftest.py --flag` not in selftest.py's known flags; `python -m nexclash.X` with no module X;
- `module.function(` where module is a toolkit module that has no such top-level name;
- a section reference that resolves to no heading: PLAYBOOK 3c / stage 2, LEARNINGS 2.6,
  BRIEFING C4 / A1, TECHNIQUES 2.6, and BRIEFING C2 #N with no item N (C2 renumbers: check it);
- a file over its size budget (BUDGET below). Why budgets: every session reads these files, and
  without a limit they only grow (LEARNINGS tripled in two weeks). Over budget -> consolidate
  (docs/MAINTAIN.md "Lesson consolidation"), do not raise the number.
WARN only: paths that do not exist (other projects' files and planned files are named on purpose)
and anything in games/*.md (game notes are history; a stale command there misleads one game only).
"""
import ast
import collections
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# bytes; set 2026-10-26 a little above that day's size: hold the line, lower them as files are condensed
BUDGET = {'CLAUDE.md': 10500, 'docs/PLAYBOOK.md': 27000, 'docs/COLOURS.md': 9000, 'docs/MAINTAIN.md': 6000,
          'docs/BRIEFING.md': 56000, 'docs/LEARNINGS.md': 90000, 'docs/TECHNIQUES.md': 68000,
          'docs/VERIFICATION.md': 82000, 'README.md': 12000}
GAME_BUDGET = 25000          # games/<game>.md; older notes over it are listed and must not grow
GAME_GRANDFATHERED = {'games/rainbow_islands.md': 72000}
SIBLING = ('nexclash/CLAUDE.md', 'nexclash/requirements.txt', 'nexclash/nexclash.py')   # ../nexclash/... in specnext sessions
SKIP_WORDS = {'the', 'and', 'is', 'with', 'or', 'in', 'to', 'only'}


def cli_flags():
    out = {}
    src = open(os.path.join(ROOT, 'nexclash.py')).read()
    m = re.search(r"\{(auto,patch[^}]*)\}", subprocess.run([sys.executable, 'nexclash.py', '--help'], cwd=ROOT,
                                                             capture_output=True, text=True).stdout)
    cmds = m.group(1).split(',') if m else re.findall(r"add_parser\('(\w+)'", src)
    for c in cmds:
        h = subprocess.run([sys.executable, 'nexclash.py', c, '--help'], cwd=ROOT, capture_output=True, text=True).stdout
        out[c] = set(re.findall(r'(?<![\w-])(--?[a-z][a-z0-9-]*)', h))
    return out


def selftest_flags():
    s = open(os.path.join(ROOT, 'selftest.py')).read()
    m = re.search(r'known = \{([^}]*)\}', s)
    return set(re.findall(r"'(--[a-z-]+)'", m.group(1))) | {'--help'}


def module_names():
    defs = {}
    for p in glob.glob(os.path.join(ROOT, 'nexclash', '*.py')) + glob.glob(os.path.join(ROOT, 'tools', '*.py')):
        try:
            t = ast.parse(open(p).read())
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


def has_section(heads, doc, sec):
    if sec.lower().startswith('stage'):
        pat = re.compile(r'^#+\s*' + re.escape(sec) + r'\b', re.I)
    else:
        pat = re.compile(r'^#+\s*(PART\s+)?' + re.escape(sec) + r'(\b|[.\s:)])', re.I)
    return any(pat.match(x) for x in heads[doc])


def main():
    os.chdir(ROOT)
    files = subprocess.run(['git', 'ls-files'], capture_output=True, text=True).stdout.split()
    files = sorted(set(files) | set(glob.glob('docs/*.md')) | {'CLAUDE.md'})
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
            for m in re.finditer(r'python3? -m nexclash\.([a-z_0-9]+)', line):
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
                if '<' not in p and '*' not in p and p not in SIBLING and not os.path.exists(p):
                    warn['path does not exist'].append('%s  %s' % (loc, p))
    for f, cap in BUDGET.items():
        if os.path.exists(f) and os.path.getsize(f) > cap:
            fail['over size budget (consolidate, docs/MAINTAIN.md)'].append('%s  %d > %d bytes' % (f, os.path.getsize(f), cap))
    for f in glob.glob('games/*.md'):
        cap = GAME_GRANDFATHERED.get(f, GAME_BUDGET)
        if os.path.getsize(f) > cap:
            fail['over size budget (consolidate, docs/MAINTAIN.md)'].append('%s  %d > %d bytes' % (f, os.path.getsize(f), cap))
    for title, d in (('WARN', warn), ('FAIL', fail)):
        for k, v in d.items():
            print('%s %s (%d)' % (title, k, len(v)))
            for x in v[:40]:
                print('     ' + x)
    print('doccheck: %s (%d docs)' % ('FAIL' if fail else 'PASS', len(docs)))
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
