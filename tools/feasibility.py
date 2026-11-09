"""Prospective feasibility evidence check, called by learncheck (no game dependencies).

New records using a new engine or new own_modules need a feasibility object; existing
records stay exempt unless they opt in. Once present, the object is always checked.
See tools/templates/feasibility.json. Links establish provenance, not technical truth.
"""
import json
from pathlib import Path
import subprocess
from urllib.parse import urlsplit


def text(value):
    return isinstance(value, str) and bool(value.strip())


def validate(value, root):
    """-> problems; local evidence is repo-relative, remote evidence is an HTTP(S) URL.
    Remote availability and whether the measurements justify the decision need review.
    """
    if not isinstance(value, dict):
        return ['feasibility must be an object (tools/templates/feasibility.json)']
    bad = []
    for key in ('decision', 'next_experiment'):
        if not text(value.get(key)):
            bad.append('feasibility.%s needs a non-empty answer' % key)
    for key in ('pacing', 'dependencies'):
        entry = value.get(key)
        if not isinstance(entry, dict):
            bad.append('feasibility.%s needs evidence, coverage and result (or not_applicable with a reason)' % key)
            continue
        if 'not_applicable' in entry:
            if not text(entry['not_applicable']) or len(entry) != 1:
                bad.append('feasibility.%s: not_applicable needs a reason and no measurement fields' % key)
            continue
        for field in ('coverage', 'result'):
            if not text(entry.get(field)):
                bad.append('feasibility.%s.%s is missing' % (key, field))
        refs = entry.get('evidence')
        if not isinstance(refs, list) or not refs:
            bad.append('feasibility.%s.evidence needs at least one link' % key)
            continue
        for ref in refs:
            if not text(ref):
                bad.append('feasibility.%s: empty or invalid evidence link' % key)
                continue
            try:
                url = urlsplit(ref)
                remote = url.scheme in ('http', 'https') and bool(url.hostname)
            except ValueError:
                bad.append('feasibility.%s: invalid evidence URL %r' % (key, ref))
                continue
            if remote:
                continue
            local = Path(root) / url.path
            if url.scheme or url.netloc or not url.path or Path(url.path).is_absolute() or \
                    not local.resolve().is_relative_to(Path(root).resolve()) or not local.is_file():
                bad.append('feasibility.%s: evidence file missing or outside repo: %s' % (key, ref))
    return bad


def check_records(current, previous, root):
    """Mappings of repo-relative record path -> JSON. previous=None: no Git baseline.
    A new record may reuse an established engine only without adding own_modules.
    Existing records are not retroactively reassessed, even when edited.
    """
    engines = {}
    for rec in (previous or {}).values():
        if rec.get('engine'):
            engines.setdefault(rec['engine'], set()).update(rec.get('own_modules', []))
    bad = []
    for path, rec in current.items():
        required = previous is not None and (
            'feasibility' in previous.get(path, {}) or
            (path not in previous and (rec.get('engine') not in engines or
             not set(rec.get('own_modules', [])).issubset(engines[rec['engine']]))))
        if 'feasibility' in rec:
            bad += ['%s: %s' % (path, p) for p in validate(rec['feasibility'], root)]
        elif required:
            bad.append('%s: feasibility evidence required (tools/templates/feasibility.json)' % path)
    return bad


def check(root, base):
    current = {p.relative_to(root).as_posix(): json.loads(p.read_text())
               for p in Path(root).glob('docs/records/*.json')}
    previous = None
    if base:
        # ls-tree, rather than changed game notes: adding a record must not evade
        # the gate by reusing an old note file or leaving it out of the PR.
        paths = subprocess.run(['git', 'ls-tree', '-r', '--name-only', base, 'docs/records'],
                               cwd=root, capture_output=True, text=True, check=True).stdout.splitlines()
        previous = {}
        for path in paths:
            if path.endswith('.json'):
                raw = subprocess.run(['git', 'show', '%s:%s' % (base, path)], cwd=root,
                                     capture_output=True, text=True, check=True).stdout
                previous[path] = json.loads(raw)
    return check_records(current, previous, root)
