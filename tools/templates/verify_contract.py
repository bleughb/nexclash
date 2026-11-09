"""New-engine verification baseline; adapt the replay loop from chuckie.verify.

Chuckie is a legacy loop example: do not copy its CMP definition. Preserve R
with HLIB_R_IN/_OUT where cheap. CMP_R is the default, not an unconditional
runtime requirement: PLAYBOOK 6 permits evidence-backed exceptions. Record
the affected state, consumer investigation, replay treatment and validation
limits before adapting CMP/the loop. Recorded R proves supplied-R behaviour;
also validate natural gameplay. Keep memory, pixels and interrupts in the engine.
"""
from nexclash import caseselect, runchecks
from nexclash.hooklib import CMP_R

CMP = CMP_R


def register_differences(original, patched):
    """Use in the engine's failure reporting, including an R-off-by-one negative."""
    return {index: (original[index], patched[index])
            for index in CMP if original[index] != patched[index]}


def check_cases(cases, exercise, checks, only=None, sample=1):
    """Example independent-case gate; adapt to the engine, do not filter live replay steps.

    cases: replay-stable (group, index, captured_state) triples, unique IDs assigned
    BEFORE selection. exercise(state, phase) returns True on success, False on
    failure; it must reset its simulator per case and perform the real comparisons.
    only: CLI --only string; sample: CLI --sample stride. Full corpus is expected
    even for a rerun: a successful sample is incomplete evidence for the full gate.
    Feed checks into the run report/stamp; exit via runchecks.exit_code(checks).
    Use caseselect.rerun(command, failures) to print the failed-case command.
    """
    if sample < 1:
        raise ValueError('sample must be >= 1')
    chosen = caseselect.parse(only)
    failures, seen, count = set(), set(), 0
    for group, index, state in cases:
        cid = caseselect.case_id(group, index)
        if cid in seen:
            raise ValueError('duplicate case id: ' + cid)
        seen.add(cid)
        if not caseselect.selected(group, index, chosen, sample):
            continue
        # Choose the phase count and salt for the engine's actual injections.
        phase = caseselect.phase(group, index, 64, 'interrupt')
        if not exercise(state, phase):
            failures.add(cid)
        count += 1
    missing = sorted(chosen - seen) if chosen is not None else []
    runchecks.measured(checks, 'independent cases', count, failures=len(failures),
                       expected=len(seen) + len(missing),
                       why=('unknown case ids: ' + ', '.join(missing)) if missing else '',
                       coverage={'only': sorted(chosen) if chosen is not None else None,
                                 'sample': sample, 'missing_ids': missing})
    return failures
