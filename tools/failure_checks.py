"""Regression checks for command failures, stale builds, contribution imports and Git worktrees."""
from contextlib import contextmanager, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(relative):
    spec = importlib.util.spec_from_file_location('failure_fixture', ROOT/relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def md5(data):
    return hashlib.md5(data).hexdigest()


@contextmanager
def repository():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)/'repo'; root.mkdir()
        def git(*args):
            return subprocess.run(['git', '-C', str(root), *map(str, args)], check=True,
                                  capture_output=True, text=True).stdout.strip()
        git('init'); git('config', 'user.name', 'Workflow Test'); git('config', 'user.email', 'workflow@example.invalid')
        (root/'nexclash').mkdir(); (root/'nexclash/shared.py').write_bytes(b'original')
        (root/'.gitignore').write_text('contrib_reports/\n')
        git('add', '.'); git('commit', '-m', 'base')
        git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        yield root, git


def archive(path, files=None, originals=None, legacy=False, corrupt=False, extras=None):
    files = files or {'nexclash/shared.py': b'contributor'}
    originals = originals if originals is not None else {'nexclash/shared.py': md5(b'original')}
    extras = extras or {}
    meta = {'game': 'example', 'files': {p: md5(data) for p, data in files.items()},
            'reports': [p.split('/', 1)[1] for p in extras if p.startswith('reports/')],
            'patches': {p.split('/', 1)[1]: md5(data) for p, data in extras.items() if p.startswith('patches/')}}
    if not legacy:
        meta.update(schema=2, source={'kind': 'git', 'commit': 'fixture'}, base_files=originals)
    if corrupt:
        meta['files'][next(iter(files))] = '0'*32
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('CONTRIBUTION.json', json.dumps(meta))
        for p, data in files.items():
            z.writestr('files/'+p, data)
        for p, data in extras.items():
            z.writestr(p, data)


class FailureChecks(unittest.TestCase):
    def test_cli_failure_and_success_exit_status(self):
        from skoolkit.snapshot import write_snapshot
        script = """import runpy, sys, types
entry, success = sys.argv[1], sys.argv[2] == 'success'
from nexclash import engines, nxcout
engines.find = lambda *args: types.SimpleNamespace(auto=lambda *args: success)
nxcout.package = lambda a: print('PACKAGED')
sys.argv = [entry] + sys.argv[3:]
runpy.run_path(entry, run_name='__main__')
"""
        with tempfile.TemporaryDirectory() as d:
            snapshot = Path(d)/'synthetic.z80'
            write_snapshot(str(snapshot), [0]*49152, ['pc=32768', 'sp=65500'], ['im=1'])
            for command in ['auto', 'verify']:
                for success in [False, True]:
                    with self.subTest(command=command, success=success):
                        args = [command, str(snapshot)] + (['--rzx', 'fake.rzx'] if command == 'verify' else [])
                        result = subprocess.run([sys.executable, '-c', script, str(ROOT/'nexclash.py'),
                                                 'success' if success else 'failure', *args], capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0 if success else 1, result.stderr)
                        self.assertEqual('PACKAGED' in result.stdout, success and command == 'auto')

    def test_finish_and_engine_failure_are_not_overridden(self):
        entry = load('nexclash.py')
        with tempfile.TemporaryDirectory() as d, patch.object(entry, '_rom_paths'), redirect_stdout(io.StringIO()):
            for report, checks, wanted in [(['Result : PASSED'], [], True), (['Boot : MISMATCH'], [], False),
                    (['Result : FAILED'], [], False), ([], [{'check': 'test', 'status': 'fail', 'why': '', 'required': True}], False)]:
                with patch.object(entry, '_CHECKS', checks):
                    self.assertEqual(entry._finish(d, 'game', report), wanted)
            a = types.SimpleNamespace(z80='fake.z80', out=d, rzx=[], quick=None)
            engine = types.SimpleNamespace(auto=lambda *args: False)
            with patch.object(entry, '_record_pin', return_value=None), patch.object(entry.Snapshot, 'get'), \
                 patch('nexclash.engines.find', return_value=engine), patch.object(entry, '_finish', return_value=True):
                self.assertIs(entry.cmd_auto(a), False)

    def test_patch_requires_a_current_sprite_build(self):
        from nexclash import userflow as u
        for outcome in ['failed', 'unchanged', 'new', 'identical-rewrite', 'absent']:
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as d:
                root = Path(d); source = root/'Game.z80'; source.write_bytes(b'synthetic snapshot')
                sprite = root/'Game_sprites.nex'
                if outcome not in ('new', 'absent'):
                    sprite.write_bytes(b'previous')
                a = types.SimpleNamespace(z80=str(source), out=d, allow_60hz=False)
                def build(args):
                    if outcome in ('new', 'identical-rewrite'):
                        # A byte-identical rebuild is valid, even with the original mtime preserved.
                        timestamp = sprite.stat().st_mtime_ns if sprite.exists() else None
                        replacement = root/'replacement'; replacement.write_bytes(b'previous')
                        os.replace(replacement, sprite)
                        if timestamp is not None:
                            os.utime(sprite, ns=(timestamp, timestamp))
                    return outcome != 'failed'
                with patch.object(u, 'verified', return_value={}), patch('nexclash.nxcout.package', return_value=None) as package, \
                     redirect_stdout(io.StringIO()) as output:
                    result = u.cmd_patch(a, build)
                self.assertEqual(result, 1 if outcome == 'failed' else 0 if outcome in ('new', 'identical-rewrite') else 2)
                self.assertEqual(package.called, outcome in ('new', 'identical-rewrite'))
                if outcome in ('failed', 'unchanged'):
                    self.assertEqual(sprite.read_bytes(), b'previous')
                    self.assertNotIn('PATCHED:', output.getvalue())

    def test_selftest_does_not_accept_outputs_from_failed_command(self):
        entry = load('selftest.py')
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); script = root/'builder.py'
            script.write_text("import pathlib,sys; pathlib.Path(sys.argv[sys.argv.index('-o')+1]).write_bytes(b'expected'); print('failure after output', file=sys.stderr); sys.exit(7)")
            rec = {'name': 'test', 'inputs': {'snapshot': {'name': 'input.z80'}},
                   'rebuild': {'cmd': 'convert'}, 'outputs': {'plain': {'file': 'out.nex', 'md5': md5(b'expected')}}}
            lines = []
            with patch.object(entry, 'NEXCLASH', str(script)), patch.object(entry, 'checks', return_value=0), \
                 patch.object(entry, '_audit_check', return_value=0):
                bad = entry.rebuild(rec, d, lines)
            self.assertEqual(bad, 1, lines)
            self.assertTrue(any(line.startswith('OK') for line in lines))
            log = Path(next(line.split('log: ', 1)[1] for line in lines if line.startswith('FAIL command')))
            try:
                self.assertIn('failure after output', log.read_text())
            finally:
                log.unlink()

    def test_worktree_uses_the_real_git_permission_probe(self):
        entry = load('selftest.py')
        with repository() as (root, git):
            remote, worktree = root.parent/'remote.git', root.parent/'worktree'
            subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
            git('remote', 'add', 'origin', remote); git('worktree', 'add', '-b', 'linked', worktree)
            environment = dict(os.environ); environment.pop('NEXCLASH_MAINTAINER', None)
            self.assertTrue((worktree/'.git').is_file())
            with patch.object(entry, 'HERE', str(worktree)), patch.object(entry, '_PUSH', None), patch.dict(os.environ, environment, clear=True):
                self.assertTrue(entry.push_access())
            # --dry-run did not create a probe branch.
            result = subprocess.run(['git', '--git-dir', str(remote), 'show-ref', '--verify', 'refs/heads/selftest-push-probe'], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            git('remote', 'remove', 'origin')
            with patch.object(entry, 'HERE', str(worktree)), patch.object(entry, '_PUSH', None), patch.dict(os.environ, environment, clear=True):
                self.assertFalse(entry.push_access())

    def test_import_refusals_do_not_touch_checkout(self):
        module = load('tools/merge_contribution.py')
        for case in ['dirty', 'untracked', 'upstream', 'bad-hash', 'legacy', 'collision', 'bad-patch', 'traversal']:
            with self.subTest(case=case), repository() as (root, git):
                path = root.parent/'contribution.zip'
                kwargs = {}
                if case == 'dirty':
                    (root/'nexclash/shared.py').write_bytes(b'maintainer work')
                if case == 'untracked':
                    (root/'draft.txt').write_text('maintainer draft')
                if case == 'upstream':
                    (root/'nexclash/shared.py').write_bytes(b'upstream'); git('commit', '-am', 'upstream')
                if case == 'bad-hash': kwargs['corrupt'] = True
                if case == 'legacy': kwargs['legacy'] = True
                if case == 'collision': kwargs['originals'] = {'nexclash/shared.py': None}
                if case == 'bad-patch': kwargs['extras'] = {'patches/invalid.txt': b'not a patch'}
                if case == 'traversal':
                    kwargs.update(files={'nexclash/../escaped.py': b'escape'}, originals={'nexclash/../escaped.py': None})
                archive(path, **kwargs)
                before = (root/'nexclash/shared.py').read_bytes(); branch = git('branch', '--show-current')
                with patch.object(module, 'ROOT', str(root)), patch.object(sys, 'argv', ['merge', str(path)]):
                    with self.assertRaises(ValueError): module.main()
                self.assertEqual((root/'nexclash/shared.py').read_bytes(), before)
                self.assertEqual(git('branch', '--show-current'), branch)
                self.assertNotIn('contrib-example', git('branch', '--list'))
                self.assertFalse((root/'contrib_reports').exists())

    def test_import_success_and_rollback(self):
        module = load('tools/merge_contribution.py')
        for fail in [False, True]:
            with self.subTest(fail=fail), repository() as (root, git):
                path = root.parent/'contribution.zip'; previous = git('branch', '--show-current')
                files = {'nexclash/shared.py': b'contributor', 'docs/new.md': b'new documentation'}
                archive(path, files, {'nexclash/shared.py': md5(b'original'), 'docs/new.md': None},
                        extras={'reports/run.txt': b'proof', 'patches/game.nxc': b'synthetic patch'})
                original = module.os.replace; calls = []
                def replace(source, destination):
                    calls.append(destination)
                    if fail and len(calls) == 2: raise OSError('injected write failure')
                    return original(source, destination)
                with patch.object(module, 'ROOT', str(root)), patch.object(sys, 'argv', ['merge', str(path)]), \
                     patch.object(module.os, 'replace', side_effect=replace), redirect_stdout(io.StringIO()):
                    if fail:
                        with self.assertRaises(OSError): module.main()
                    else: module.main()
                if fail:
                    self.assertEqual((root/'nexclash/shared.py').read_bytes(), b'original')
                    self.assertEqual(git('branch', '--show-current'), previous)
                    self.assertNotIn('contrib-example', git('branch', '--list'))
                    self.assertEqual(git('status', '--porcelain'), '')
                else:
                    self.assertEqual((root/'nexclash/shared.py').read_bytes(), b'contributor')
                    self.assertEqual(git('branch', '--show-current'), 'contrib-example')
                    self.assertEqual((root/'contrib_reports/contrib-example/run.txt').read_bytes(), b'proof')
                    self.assertEqual((root/'contrib_reports/contrib-example/game.nxc').read_bytes(), b'synthetic patch')

    def test_legacy_archive_can_add_a_new_file(self):
        module = load('tools/merge_contribution.py')
        with repository() as (root, git):
            path = root.parent/'legacy.zip'
            archive(path, files={'nexclash/new.py': b'new module'}, legacy=True)
            with patch.object(module, 'ROOT', str(root)), patch.object(sys, 'argv', ['merge', str(path)]), redirect_stdout(io.StringIO()):
                module.main()
            self.assertEqual((root/'nexclash/new.py').read_bytes(), b'new module')
            self.assertEqual((root/'nexclash/shared.py').read_bytes(), b'original')

    def test_export_import_roundtrip_on_another_worktree(self):
        from nexclash import userflow as u
        module = load('tools/merge_contribution.py')
        with repository() as (root, git):
            worktree = root.parent/'receiving'; git('worktree', 'add', '--detach', worktree, 'HEAD')
            (root/'nexclash/shared.py').write_bytes(b'contributor'); git('commit', '-am', 'contribution')
            path = root.parent/'contribution.zip'
            a = types.SimpleNamespace(base=None, output=str(path), name='example', note='', report=[])
            with patch.object(u, 'ROOT', str(root)), patch.object(u, 'MANIFEST', str(root/'MANIFEST.json')), \
                 patch.object(u, 'CONTRIB', str(root/'absent.json')), redirect_stdout(io.StringIO()):
                self.assertEqual(u.cmd_contribute(a), 0)
            with zipfile.ZipFile(path) as z:
                meta = json.loads(z.read('CONTRIBUTION.json'))
                self.assertEqual(meta['base_files'], {'nexclash/shared.py': md5(b'original')})
                self.assertEqual(meta['source']['kind'], 'git')
            with patch.object(module, 'ROOT', str(worktree)), patch.object(sys, 'argv', ['merge', str(path)]), redirect_stdout(io.StringIO()):
                module.main()
            self.assertEqual((worktree/'nexclash/shared.py').read_bytes(), b'contributor')


if __name__ == '__main__':
    unittest.main(verbosity=2)
