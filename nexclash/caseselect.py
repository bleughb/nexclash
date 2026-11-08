"""Failed-case reruns for a verifier (docs/PLAYBOOK.md 6): stable case ids, deterministic samples.

A case is (group, index), printed 'group:index' (Inferno: level:state). What a case exercises (CTC phase, injected
interrupts, ...) comes from phase(), which depends on the case alone: the case behaves the same run alone, in a
sample or in the full set, so a failure reproduces in seconds. The ladder: failed cases, a sample, the full gate once."""
import zlib


def case_id(group, index):
    return '%s:%d' % (group, index)


def parse(spec):
    """'3:182,6:27' -> {'3:182', '6:27'}; empty or None -> None (no restriction)."""
    if not spec:
        return None
    out = set()
    for item in spec.split(','):
        group, sep, index = item.strip().rpartition(':')
        if not sep or not group or not index.isdigit():
            raise ValueError('case %r: want group:index' % item)
        out.add(case_id(group, int(index)))
    return out


def selected(group, index, only=None, sample=1):
    """only (parse()) wins over sample: a case listed by id always runs."""
    if only is not None:
        return case_id(group, index) in only
    return index % sample == 0


def phase(group, index, n, salt=''):
    """A value 0..n-1 fixed by the case: never a running counter, which depends on what else was selected."""
    return zlib.crc32(('%s|%s' % (salt, case_id(group, index))).encode()) % n


def rerun(command, failures, flag='--only'):
    """The command line that reproduces just these failures; None when there are none."""
    return '%s %s %s' % (command, flag, ','.join(sorted(failures))) if failures else None


def selfcheck():
    """-> failures (selftest --tools)"""
    bad = []
    cases = [(g, i) for g in ('1', '6') for i in range(200)]
    full = {case_id(g, i): phase(g, i, 64, 'ctc') for g, i in cases}
    tenth = {case_id(g, i): phase(g, i, 64, 'ctc') for g, i in cases if selected(g, i, sample=10)}
    only = parse('6:27, 1:182')
    alone = {case_id(g, i): phase(g, i, 64, 'ctc') for g, i in cases if selected(g, i, only)}
    if len(tenth) != 40 or any(full[k] != v for k, v in tenth.items()) or sorted(alone) != ['1:182', '6:27'] or \
            any(full[k] != v for k, v in alone.items()):
        bad.append('a case changes with the selection')
    if len(set(full.values())) < 32:
        bad.append('phase does not spread')
    if selected('1', 5, {'1:5'}, sample=10) is not True or parse('') is not None:
        bad.append('only / empty spec')
    for spec in ('12', ':3', 'a:b'):
        try:
            parse(spec)
            bad.append('bad case %r accepted' % spec)
        except ValueError:
            pass
    if rerun('v', {'6:27', '1:2'}) != 'v --only 1:2,6:27' or rerun('v', set()) is not None:
        bad.append('rerun')
    return bad
