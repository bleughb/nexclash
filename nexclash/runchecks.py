"""A run's check status, structured (docs/REFACTOR.md 7): what each automatic check of `auto` proved, so a stamp and
the .nxc's PRF1 never rest on report text alone. nexclash.py writes NAME_checks.json beside the report and its
`Checks    :` line; selftest's verification (stamps) and nxcout (PRF1) read them.

Statuses: pass; fail (a fault: the run FAILED); incomplete (the check raised, a recording it never replayed, an early
partial replay, a ROM select it does not model: the builds stand, their proof is not full); waived (a record's named
exception, its pin: the game verifies as it was verified); not run (no recordings, a rebuild: nothing was claimed);
not measured (the check ran over nothing: no rows, states or cases; a required one blocks the claim and its stamp);
not applicable (this build has no such thing, with the reason: distinct from missing coverage).
Accepted and bounded, with their names in the coverage: a replay whose port readings end in the recording's last
frame ('last frame'), and the record's rom_paths_known (KNOWN, not faults)."""
import json
import os

DONE = ('pass', 'waived', 'not run', 'not applicable')
RUN = []                    # this process's run: nexclash.py's _CHECKS; an engine adds its own (Starquake's negatives)


def add(checks, name, status, why='', required=True, coverage=None):
    if status == 'not applicable' and not why:
        raise ValueError('%s: not applicable needs the reason' % name)
    checks.append(dict(check=name, status=status, why=why, required=required, coverage=coverage or {}))
    return checks[-1]


def measured(checks, name, count, failures=0, expected=None, why='', required=True, coverage=None):
    """A check over rows / states / cases: empty evidence can never be a pass. count 0 -> not measured; fewer than
    expected -> incomplete; failures -> fail (it outranks the rest); else pass. An inapplicable check: add(..,
    'not applicable', reason). -> the entry."""
    if failures:
        status = 'fail'
    elif not count:
        status, why = 'not measured', why or 'no rows, states or cases'
    elif expected is not None and count < expected:
        status, why = 'incomplete', why or '%d of %d' % (count, expected)
    else:
        status = 'pass'
    return add(checks, name, status, why, required, dict(coverage or {}, count=count, failures=failures))


def rom_paths(res, rzxs, nexes):
    """nextboot.rom_paths' result -> (status, why, coverage) for the check over every build and recording."""
    fails, probs, cov = [], [], {}
    for nex in nexes:
        b = os.path.basename(nex)
        if nex not in res:
            probs.append('%s: not checked' % b)
            continue
        kind, _lines, faults, cover = res[nex]
        if kind == 'boot':
            fails.append('%s: boot failed in the Next model' % b)
            continue
        if faults:
            fails.append('%s: faults in %s' % (b, ', '.join(sorted(faults))))
        cov[b] = {}
        for r in rzxs:
            n = os.path.basename(r)
            c = cover.get(n)
            if c is None:
                probs.append('%s: %s never replayed' % (b, n))
                continue
            cov[b][n] = dict(frames=c['frames'], of=c['of'], how=c['how'])
            if 'start_pc' in c:
                cov[b][n].update(start_pc=c['start_pc'], entry_frame=c['entry_frame'])
            if c['how'] == 'partial' or not c['frames']:
                probs.append('%s: %s partial, frames 1-%d of %d' % (b, n, c['frames'], c['of']))
            if c.get('unmodelled'):
                probs.append('%s: %s ROM select %s not modelled' % (b, n, ','.join(map(str, c['unmodelled']))))
    status = 'fail' if fails else 'incomplete' if probs else 'pass'
    return status, '; '.join(fails + probs), cov


def complete(checks):
    return all(c['status'] in DONE for c in checks if c['required'])


def line(checks):
    """The report's `Checks    :` line."""
    if not checks:
        return 'INCOMPLETE: no check status'
    bad = [c for c in checks if c['required'] and c['status'] not in DONE]
    parts = ', '.join('%s %s%s' % (c['check'], c['status'], (' (%s)' % c['why'][:160]) if c['why'] else '') for c in checks)
    return ('COMPLETE: ' if not bad else '%s: ' % ('FAILED' if any(c['status'] == 'fail' for c in bad) else 'INCOMPLETE')) + parts


def exit_code(checks):
    """For a verifier's own command line: 0 only when every required check is done, 1 a failure, 2 incomplete or not
    measured; no checks at all is 2."""
    if not checks:
        return 2
    if any(c['status'] == 'fail' for c in checks):
        return 1
    return 0 if complete(checks) else 2


def selfcheck():
    """Empty evidence never passes (selftest --tools). -> failures"""
    bad = []
    for label, kw, status, code in (('empty', dict(count=0), 'not measured', 2), ('short', dict(count=3, expected=4), 'incomplete', 2),
                                    ('fail', dict(count=3, failures=1), 'fail', 1), ('fail, empty', dict(count=0, failures=1), 'fail', 1),
                                    ('full', dict(count=4, expected=4), 'pass', 0)):
        c = []
        if measured(c, 'x', **kw)['status'] != status or exit_code(c) != code or complete(c) != (code == 0):
            bad.append('measured %s' % label)
    c = []
    add(c, 'x', 'not applicable', 'no sound hook')
    if not complete(c) or exit_code(c) or 'not applicable' not in line(c):
        bad.append('not applicable is not done')
    try:
        add([], 'x', 'not applicable')
        bad.append('not applicable without a reason')
    except ValueError:
        pass
    if exit_code([]) != 2:
        bad.append('no checks at all')
    c = []
    measured(c, 'x', 0, required=False)
    if not complete(c):
        bad.append('an optional empty check blocks')
    return bad


def path(out, name):
    return os.path.join(out, name + '_checks.json')


def write(out, name, checks, extra=None):
    d = dict(schema=1, complete=complete(checks), checks=checks)
    d.update(extra or {})
    json.dump(d, open(path(out, name), 'w'), indent=1)


def read(out, name):
    """-> the checks file's dict, or None (a run that wrote none: an engine that stopped before _finish)."""
    try:
        return json.load(open(path(out, name)))
    except (OSError, ValueError):
        return None
