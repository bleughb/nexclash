"""A run's check status, structured (docs/REFACTOR.md 7): what each automatic check of `auto` proved, so a stamp and
the .nxc's PRF1 never rest on report text alone. nexclash.py writes NAME_checks.json beside the report and its
`Checks    :` line; selftest's verification (stamps) and nxcout (PRF1) read them.

Statuses: pass; fail (a fault: the run FAILED); incomplete (the check raised, a recording it never replayed, an early
partial replay, a ROM select it does not model: the builds stand, their proof is not full); waived (a record's named
exception, its pin: the game verifies as it was verified); not run (no recordings, a rebuild: nothing was claimed).
Accepted and bounded, with their names in the coverage: a replay whose port readings end in the recording's last
frame ('last frame'), and the record's rom_paths_known (KNOWN, not faults)."""
import json
import os

DONE = ('pass', 'waived', 'not run')
RUN = []                    # this process's run: nexclash.py's _CHECKS; an engine adds its own (Starquake's negatives)


def add(checks, name, status, why='', required=True, coverage=None):
    checks.append(dict(check=name, status=status, why=why, required=required, coverage=coverage or {}))
    return checks[-1]


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
