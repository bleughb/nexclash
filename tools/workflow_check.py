"""Workflow regression checks; optional --package ZIP checks the actual release archive."""
import argparse
import hashlib
import importlib.util
import json
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
PACKAGE = None


def load(path):
    spec = importlib.util.spec_from_file_location('workflow_fixture', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkflowChecks(unittest.TestCase):
    def test_runner_keeps_failure_and_early_warning(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / 'run.log'
            result = subprocess.run([sys.executable, str(ROOT/'tools/run_logged.py'), '--log', str(log), '--',
                sys.executable, '-c', "print('WARNING early'); print('line\\n'*100); raise SystemExit(7)"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 7)
            self.assertIn('WARNING early', result.stdout)
            self.assertLess(len(result.stdout.splitlines()), 55)
            self.assertEqual(json.loads(Path(str(log)+'.status.json').read_text())['exit_code'], 7)
            self.assertGreater(len(log.read_text().splitlines()), 100)

    def test_runner_success_and_launch_failure(self):
        with tempfile.TemporaryDirectory() as d:
            for command, expected in [([sys.executable, '-c', 'pass'], 0), ([str(Path(d)/'absent')], 127)]:
                log = Path(d)/'run.log'
                result = subprocess.run([sys.executable, str(ROOT/'tools/run_logged.py'), '--log', str(log), '--',
                                         *command], capture_output=True)
                self.assertEqual(result.returncode, expected)
                self.assertEqual(json.loads(Path(str(log)+'.status.json').read_text())['exit_code'], expected)

    def test_recognition_skips_expensive_work_and_full_opt_in(self):
        from nexclash import survey
        fake = types.SimpleNamespace(memory=bytearray(65536), ram=lambda *args: bytearray(49152))
        with tempfile.TemporaryDirectory() as d, patch('skoolkit.snapshot.Snapshot.get', return_value=fake), \
             patch('nexclash.snapinfo.report', return_value='snapshot'), \
             patch('nexclash.engines.find', return_value=types.SimpleNamespace(__name__='nexclash.example')), \
             patch('nexclash.identify.identify', return_value={'engine': 'unknown'}), \
             patch('nexclash.build.plain', side_effect=RuntimeError('full analysis reached')) as plain:
            _, report = survey.survey('example.z80', ['missing.rzx'], out=d)
            self.assertEqual(report['mode'], 'recognition-only')
            plain.assert_not_called()
            with self.assertRaisesRegex(RuntimeError, 'full analysis reached'):
                survey.survey('example.z80', out=d, full=True)

    def test_package_asset_exceptions_are_exact(self):
        module = load(ROOT/'tools/make_package.py')
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/'tools').mkdir(); (root/'assets').mkdir()
            asset = root/'assets/art.bin'; asset.write_bytes(b'owner art')
            (root/'tools/package_assets.json').write_text(json.dumps({'sha256': {
                'assets/art.bin': hashlib.sha256(asset.read_bytes()).hexdigest()}}))
            self.assertEqual(module.rejected_files(['assets/art.bin'], d), [])
            asset.write_bytes(b'other data')
            (root/'game.z80').write_bytes(b'snapshot')
            self.assertEqual(module.rejected_files(['assets/art.bin', 'game.z80'], d),
                             ['assets/art.bin', 'game.z80'])

    def test_new_template_compares_r(self):
        from skoolkit.simutils import R, T, MEMPTR
        module = load(ROOT/'tools/templates/verify_contract.py')
        original, changed = [0]*32, [0]*32
        changed[R] = 1
        self.assertIn(R, module.register_differences(original, changed))
        self.assertNotIn(T, module.CMP)
        self.assertNotIn(MEMPTR, module.CMP)

    def test_committed_git_contribution(self):
        from nexclash import userflow
        with tempfile.TemporaryDirectory() as d:
            def git(*args):
                return subprocess.run(['git', '-C', d, *args], capture_output=True, text=True, check=True).stdout.strip()
            git('init'); git('config', 'user.name', 'Workflow Test'); git('config', 'user.email', 'workflow@example.invalid')
            p = Path(d)/'README.md'; p.write_text('base'); git('add', '.'); git('commit', '-m', 'base')
            base = git('rev-parse', 'HEAD'); git('update-ref', 'refs/remotes/origin/main', base)
            p.write_text('contributor work'); git('add', '.'); git('commit', '-m', 'work')
            with patch.object(userflow, 'ROOT', d), patch.object(userflow, 'MANIFEST', str(Path(d)/'MANIFEST.json')):
                self.assertEqual(userflow.changed_files(), ['README.md'])

    def test_release_archive_contribution(self):
        if not PACKAGE:
            self.skipTest('use --package ZIP to smoke-test the built archive')
        with tempfile.TemporaryDirectory() as d, zipfile.ZipFile(PACKAGE) as archive:
            archive.extractall(d)
            root = next(Path(d).iterdir())
            manifest = json.loads((root/'MANIFEST.json').read_text())
            self.assertEqual((root/'VERSION').read_text().strip(), manifest['version'])
            self.assertEqual(root.name, 'nexclash-'+manifest['version'])
            for name, expected in manifest['files'].items():
                self.assertEqual(hashlib.md5((root/name).read_bytes()).hexdigest(), expected, name)
            module = load(root/'nexclash/userflow.py')
            p = root/'README.md'; p.write_text(p.read_text()+'\nWorkflow smoke change.\n')
            self.assertEqual(module.changed_files(), ['README.md'])
            output = Path(d)/'contribution.zip'
            args = types.SimpleNamespace(base=None, output=str(output), name='smoke', note='', report=[])
            module.cmd_contribute(args)
            with zipfile.ZipFile(output) as contribution:
                meta = json.loads(contribution.read('CONTRIBUTION.json'))
                self.assertEqual(set(meta['files']), {'README.md'})
                self.assertEqual(meta['package_version'], manifest['version'])
                self.assertEqual(contribution.read('files/README.md'), p.read_bytes())


def main():
    global PACKAGE
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package')
    args = ap.parse_args()
    PACKAGE = args.package
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WorkflowChecks)
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
