#!/usr/bin/env python3
"""The learning loop's checkable part (docs/LEARNING.md): every lesson has a disposition that
resolves, technique use is recorded, kept probes are complete, new cards carry their evidence.

    python tools/learncheck.py            exit 0 = PASS, 1 = FAIL (doccheck runs check() too)
    python tools/learncheck.py --usage    per card / probe: in how many distinct games, how often it
                                          was used, helped, did not help, was corrected
    python tools/learncheck.py --selfcheck  the parser and counting rules on synthetic notes (CI)

Checks STRUCTURE, never technical truth. Scope (docs/LEARNING.md 6): games/<game>.md files with a
"## Lessons" section, and every game file a record names (docs/records "doc") that changed against
origin/main: it must have "## Lessons" + "## Technique use", and a lesson added or changed since the
merge base - or an explicit `- [none: <why>]` line ("no new findings"). Untouched old files are left
alone. Lessons and technique-use lines are "- " bullets (continuation lines indented); any other
line there fails, so nothing is silently skipped. Under CI ($CI set) a missing merge base fails
instead of skipping the changed-file checks. Kept probes: each is in selftest.py's PROBE_SMOKE
registry with a smoke-test function that tools_check runs (GPT6 review, 2026-10-27).
Not a game dependency (docs/records): changing it re-verifies nothing.
"""
import ast
import collections
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TDIR = os.path.join(ROOT, 'docs', 'techniques')
PDIR = os.path.join(ROOT, 'tools', 'probes')
NOT_CARDS = {'STANDARD.md', 'CHANGELOG.md'}
USE = ('used', 'helped', 'no help', 'corrected')
PROBE_FIELDS = ('Invocation:', 'Limits:', 'Origin:', 'Smoke test:')
TAG = re.compile(r'\[(card|doc|tool|backlog|probe|local|deferred|none)\b([^\]]*)\]')


def cards():
    """-> {id: (meta dict, [headings], text)}"""
    out = {}
    for p in sorted(glob.glob(os.path.join(TDIR, '*.md'))):
        if os.path.basename(p) in NOT_CARDS:
            continue
        t = open(p).read()
        m = re.search(r'```json\s*(\{.*?\})\s*```', t, re.S)
        meta = json.loads(m.group(1)) if m else {}
        heads = [h.strip('# ').strip() for h in re.findall(r'^#{1,4} .+$', t, re.M)]
        out[os.path.splitext(os.path.basename(p))[0]] = (meta, heads, t)
    return out


def probes():
    """-> {file name: (docstring fields present, listed in README)}"""
    readme = open(os.path.join(PDIR, 'README.md')).read() if os.path.exists(os.path.join(PDIR, 'README.md')) else ''
    out = {}
    for p in sorted(glob.glob(os.path.join(PDIR, '*.py'))):
        n = os.path.basename(p)
        t = open(p).read()
        out[n] = ([f for f in PROBE_FIELDS if f not in t], ('| %s |' % n) in readme)
    return out


def _ctx():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import doccheck
    os.chdir(ROOT)
    heads, c2 = doccheck.headings()
    return {'heads': heads, 'c2': c2, 'mods': doccheck.module_names(), 'cli': doccheck.cli_flags(),
            'has_section': doccheck.has_section}


def _section(text, title, stray=None):
    """Items of the '## title' section: "- " bullets with their indented continuation lines joined.
    stray (a list): every other non-blank line is appended to it (unrecognised formatting)."""
    m = re.search(r'^## %s\s*$(.*?)(?=^## |\Z)' % re.escape(title), text, re.M | re.S)
    if not m:
        return None
    items, cur = [], None
    for line in m.group(1).splitlines():
        if line.startswith('- '):
            cur = [line[2:].strip()]
            items.append(cur)
        elif cur is not None and line.startswith('  ') and line.strip():
            cur.append(line.strip())
        elif not line.strip():
            cur = None
        elif stray is not None:
            stray.append(line.strip())
    return [' '.join(x) for x in items]


def _tool_ok(ref, ctx):
    ref = ref.strip().strip('`')
    m = re.match(r'(?:python3? )?nexclash\.py ([a-z]+)', ref)
    if m:
        return m.group(1) in ctx['cli']
    m = re.match(r'(?:python3? -m )?nexclash\.([a-z_0-9]+)$', ref)
    if m:
        return m.group(1) in ctx['mods']
    m = re.match(r'([a-z_0-9]+)\.([A-Za-z_][A-Za-z_0-9]*)(\(\))?$', ref)
    if m and m.group(1) in ctx['mods']:
        return m.group(2) in ctx['mods'][m.group(1)]
    return os.path.exists(os.path.join(ROOT, ref))


def _check_tag(kind, arg, game_text, cs, ps, ctx):
    """-> problem text or None"""
    arg = arg.strip()
    if kind == 'card':
        m = re.match(r'([\w.-]+)\s+§\s*(.+)$', arg)
        if not m:
            return 'card tag needs "[card <id> §<section>]"'
        cid, sec = m.groups()
        if cid not in cs:
            return 'no card %s' % cid
        if not any(h.lower().startswith(sec.strip().lower()) for h in cs[cid][1]):
            return 'card %s has no section "%s"' % (cid, sec)
    elif kind == 'doc':
        m = re.match(r'(PLAYBOOK|LEARNINGS|BRIEFING|TECHNIQUES)\s+(.+)$', arg)
        if m:
            doc, sec = m.groups()
            n = re.match(r'C2 #(\d+)', sec)
            if n:
                return None if int(n.group(1)) in ctx['c2'] else 'no BRIEFING C2 #%s' % n.group(1)
            return None if ctx['has_section'](ctx['heads'], doc, sec.split()[0]) else 'no %s %s' % (doc, sec)
        m = re.match(r'((?:docs|tools)/[\w./-]+\.md)\s+§\s*(.+)$', arg)
        if not m:
            return 'doc tag needs "[doc BRIEFING A1]" or "[doc docs/X.md §Heading]"'
        p, sec = m.groups()
        if not os.path.exists(os.path.join(ROOT, p)):
            return 'no file %s' % p
        hs = [h.strip('# ').strip().lower() for h in open(os.path.join(ROOT, p)) if h.startswith('#')]
        if not any(h.startswith(sec.strip().lower()) for h in hs):
            return '%s has no section "%s"' % (p, sec)
    elif kind == 'tool':
        if not arg or not _tool_ok(arg, ctx):
            return 'tool "%s" does not resolve (a request not built yet is [backlog C2 #N])' % arg
    elif kind == 'backlog':
        m = re.match(r'C2 #(\d+)$', arg)
        if not m or int(m.group(1)) not in ctx['c2']:
            return 'backlog tag needs an existing "[backlog C2 #N]"'
    elif kind == 'probe':
        n = os.path.basename(arg)
        if not arg.startswith('tools/probes/') or n not in ps:
            return 'no probe %s' % arg
        missing, listed = ps[n]
        if missing or not listed:
            return 'probe %s: %s' % (n, ', '.join(missing + ([] if listed else ['not in tools/probes/README.md'])))
    elif kind == 'none':
        if not re.match(r':\s*\S.{6,}', arg):
            return 'none tag needs a reason "[none: <why there is no new finding>]"'
    elif kind == 'local':
        if not re.match(r':\s*\S.{6,}', arg):
            return 'local tag needs a reason "[local: <reason>]"'
    elif kind == 'deferred':
        m = re.match(r'(C2 #(\d+)|Open)\s*:\s*reconsider when\s+\S.{4,}$', arg)
        if not m:
            return 'deferred tag needs "[deferred C2 #N|Open: reconsider when <condition>]"'
        if m.group(2) and int(m.group(2)) not in ctx['c2']:
            return 'no BRIEFING C2 #%s' % m.group(2)
        if m.group(1) == 'Open' and not re.search(r'^## Open', game_text, re.M):
            return 'no "## Open" section to defer to'
    return None


def merge_base():
    """The merge base with origin/main, or None (no git / no origin/main)."""
    try:
        return subprocess.run(['git', 'merge-base', 'HEAD', 'origin/main'], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def changed_games(base=None):
    """Game files changed against origin/main (merge base, incl. the working tree); None: no git."""
    base = base or merge_base()
    if not base:
        return None
    try:
        out = subprocess.run(['git', 'diff', '--name-only', base], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return None
    return {f for f in out if f.startswith('games/') and f.endswith('.md')}


def _at_base(base, rel):
    """The file's text at the merge base ('' if it did not exist)."""
    r = subprocess.run(['git', 'show', '%s:%s' % (base, rel)], cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ''


def record_docs():
    """games/<doc> of every evidence record."""
    return {'games/' + json.load(open(p)).get('doc', '') for p in glob.glob(os.path.join(ROOT, 'docs', 'records', '*.json'))}


def probe_registry():
    """selftest.py's PROBE_SMOKE (read, not imported) -> ({probe file: smoke function}, module-level
    function names, True when tools_check runs the registry)."""
    tree = ast.parse(open(os.path.join(ROOT, 'selftest.py')).read())
    reg, funcs, runs = {}, set(), False
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            funcs.add(node.name)
            if node.name == 'tools_check':
                runs = any(isinstance(n, ast.Name) and n.id == 'PROBE_SMOKE' for n in ast.walk(node))
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PROBE_SMOKE' for t in node.targets):
            if isinstance(node.value, ast.Dict):
                for k, v in zip(node.value.keys, node.value.values):
                    if isinstance(k, ast.Constant) and isinstance(v, ast.Name):
                        reg[k.value] = v.id
    return reg, funcs, runs


def check(ctx=None):
    """-> list of problems (strings)."""
    ctx = ctx or _ctx()
    cs, ps = cards(), probes()
    bad = []
    reg, funcs, runs = probe_registry()
    for n, (missing, listed) in ps.items():
        if missing:
            bad.append('tools/probes/%s: docstring lacks %s' % (n, ', '.join(missing)))
        if not listed:
            bad.append('tools/probes/%s: not listed in tools/probes/README.md' % n)
        if n not in reg:
            bad.append('tools/probes/%s: no smoke test in selftest.py PROBE_SMOKE' % n)
        elif reg[n] not in funcs:
            bad.append('tools/probes/%s: PROBE_SMOKE names %s, no such function in selftest.py' % (n, reg[n]))
    for n in sorted(set(reg) - set(ps)):
        bad.append('selftest.py PROBE_SMOKE: %s is not a probe in tools/probes/' % n)
    if reg and not runs:
        bad.append('selftest.py tools_check never runs PROBE_SMOKE (the probes\' smoke tests)')
    base = merge_base()
    changed = changed_games(base)
    if changed is None and os.environ.get('CI'):
        bad.append('no merge base with origin/main (CI checkout needs fetch-depth: 0): changed game files not checked')
    rdocs = record_docs()
    for g in sorted(glob.glob(os.path.join(ROOT, 'games', '*.md'))):
        rel = os.path.relpath(g, ROOT)
        t = open(g).read()
        stray = []
        lessons = _section(t, 'Lessons', stray)
        revisited = changed is not None and rel in changed and rel in rdocs
        if lessons is None:
            if changed is not None and rel in changed and re.search(r'^## Lesson candidates', t, re.M):
                bad.append('%s: changed but still "## Lesson candidates": migrate to "## Lessons" with '
                           'dispositions (docs/LEARNING.md)' % rel)
            elif revisited:
                bad.append('%s: changed but no "## Lessons" section (docs/LEARNING.md 2; nothing new: '
                           '"- [none: <why>]")' % rel)
            continue
        if re.search(r'^## Lesson candidates', t, re.M):
            bad.append('%s: both "## Lessons" and "## Lesson candidates"' % rel)
        for line in stray:
            bad.append('%s: "## Lessons": not a "- " bullet (or an indented continuation): %s' % (rel, line[:70]))
        if not lessons:
            bad.append('%s: "## Lessons" is empty (nothing new: "- [none: <why>]")' % rel)
        if revisited and base:
            old = set(_section(_at_base(base, rel), 'Lessons') or [])
            if not [x for x in lessons if x not in old]:
                bad.append('%s: changed since %s but no lesson added or changed (nothing new: add '
                           '"- [none: <why>]", docs/LEARNING.md 2)' % (rel, base[:7]))
        for i, item in enumerate(lessons, 1):
            tags = TAG.findall(item[:400])
            if not tags or not item.startswith('['):
                bad.append('%s: lesson %d has no disposition tag at its start: %s' % (rel, i, item[:70]))
                continue
            for kind, arg in tags:
                p = _check_tag(kind, arg, t, cs, ps, ctx)
                if p:
                    bad.append('%s: lesson %d: %s' % (rel, i, p))
        ustray = []
        use = _section(t, 'Technique use', ustray)
        for line in ustray:
            bad.append('%s: "## Technique use": not a "- " bullet: %s' % (rel, line[:70]))
        if use is None:
            bad.append('%s: "## Lessons" needs "## Technique use" (docs/LEARNING.md 5)' % rel)
        else:
            for item in use:
                m = re.match(r'([\w./-]+):\s*(used|helped|no help|corrected)\b', item)
                if not m:
                    bad.append('%s: technique use line "%s" (want "<card id | probe>: used | helped | '
                               'no help: why | corrected: what")' % (rel, item[:60]))
                elif m.group(1) not in cs and os.path.basename(m.group(1)) not in ps:
                    bad.append('%s: technique use names no card or probe: %s' % (rel, m.group(1)))
    for cid, (meta, heads, text) in cs.items():
        if meta.get('schema', 3) < 4:
            continue                          # migrated when next revised (docs/LEARNING.md 4)
        if meta.get('lifecycle') == 'candidate':
            for k in ('**Assumptions.**', '**Validation gap.**'):
                if k not in text:
                    bad.append('card %s (schema 4 candidate): no %s line' % (cid, k))
            if not meta.get('examples') and not meta.get('sources'):
                bad.append('card %s (schema 4 candidate): no source (examples or sources)' % cid)
        elif meta.get('lifecycle') == 'active' and not _active_evidence(cid):
            bad.append('card %s (active): no record with a "pass" result for an application of it' % cid)
    return bad


def _active_evidence(cid):
    for p in glob.glob(os.path.join(ROOT, 'docs', 'records', '*.json')):
        r = json.load(open(p))
        apps = {t.get('application') for t in r.get('techniques', []) if t.get('id') == cid}
        if any(x.get('application') in apps and x.get('status') == 'pass' for x in r.get('results', [])):
            return True
    return False


def usage_counts(texts=None):
    """-> {card or probe: Counter(uses, used, helped, ...)}, {card or probe: set of games}. A game with
    several lines for one card counts once in the games (cross-game evidence is distinct games).
    texts: {game file name: text} instead of games/*.md."""
    cnt, games = collections.defaultdict(collections.Counter), collections.defaultdict(set)
    if texts is None:
        texts = {os.path.basename(g): open(g).read() for g in glob.glob(os.path.join(ROOT, 'games', '*.md'))}
    for g, text in texts.items():
        for item in _section(text, 'Technique use') or []:
            m = re.match(r'([\w./-]+):\s*(used|helped|no help|corrected)\b', item)
            if m:
                cnt[m.group(1)][m.group(2)] += 1
                cnt[m.group(1)]['uses'] += 1
                games[m.group(1)].add(g)
    return cnt, games


def usage():
    cnt, games = usage_counts()
    for k in sorted(cnt):
        print('%-40s games %d (%s), %s' % (k, len(games[k]), ', '.join(sorted(games[k])),
                                          ', '.join('%s %d' % (u, cnt[k][u]) for u in ('uses',) + USE if cnt[k][u])))


def selfcheck():
    """The parser and counting rules on synthetic notes (no git, no game files) -> list of failures."""
    bad = []
    stray = []
    t = '## Lessons\n- [local: one line\n  continued here]\n* starred\nplain paragraph\n\n## Open\n- x\n'
    items = _section(t, 'Lessons', stray)
    if items != ['[local: one line continued here]'] or stray != ['* starred', 'plain paragraph']:
        bad.append('lesson parsing: %r / %r' % (items, stray))
    if _section('## Open\n- x\n', 'Lessons') is not None:
        bad.append('missing section not None')
    for arg, ok in ((': hardware report only, nothing new', True), ('', False), (':  ', False)):
        if (_check_tag('none', arg, '', {}, {}, {}) is None) != ok:
            bad.append('none tag %r' % arg)
    use = '## Technique use\n- patch.a: helped\n- patch.a: helped (again)\n- patch.b: used\n'
    cnt, games = usage_counts({'g1.md': use, 'g2.md': '## Technique use\n- patch.b: no help: why\n'})
    if (len(games['patch.a']), cnt['patch.a']['uses'], len(games['patch.b']), cnt['patch.b']['uses']) != (1, 2, 2, 2):
        bad.append('usage: distinct games vs uses %r %r' % (dict(cnt), dict(games)))
    return bad


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '--selfcheck' in argv:
        bad = selfcheck()
        for b in bad:
            print('FAIL ' + b)
        print('learncheck selfcheck: %s' % ('FAIL' if bad else 'PASS'))
        return 1 if bad else 0
    if '--usage' in argv:
        usage()
        return 0
    bad = check()
    for b in bad:
        print('FAIL ' + b)
    print('learncheck: %s' % ('FAIL' if bad else 'PASS'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
