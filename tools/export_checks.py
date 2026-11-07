"""Contribution baseline, completeness and generated-file discovery regression checks."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

from tools.failure_checks import repository, load
from nexclash import userflow as u


def args(path):
    return types.SimpleNamespace(base=None, output=str(path), name='example', note='', report=[], exclude=None)


def noise(root):
    paths = ['.venv/dependency.py', 'tools/.venv/dependency.py', 'venv/dependency.py', 'env/dependency.py',
             '.pytest_cache/cached.py', '.mypy_cache/cached.py', 'tools/__pycache__/cached.py',
             'node_modules/package/index.js', 'dist/bundle.py', 'build/output.py',
             'Game_nexclash/Game_report.txt', 'Game_session/SESSION.md', 'Game_survey/survey.json',
             'Game_out/result.json', 'contrib_reports/example/report.txt', 'out_example/result.json',
             '.recolour_example/colours.json', 'run.log']
    for name in paths:
        path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('generated data')


class ExportChecks(unittest.TestCase):
    def test_upstream_merge_is_not_exported_and_stale_override_is_refused(self):
        with repository() as (root, git):
            start = git('rev-parse', 'HEAD'); branch = git('branch', '--show-current')
            git('branch', 'upstream')
            (root/'nexclash/shared.py').write_bytes(b'contributor'); git('commit', '-am', 'contributor')
            before_refresh = git('rev-parse', 'HEAD')
            git('checkout', 'upstream'); (root/'README.md').write_text('upstream-only change')
            git('add', '.'); git('commit', '-m', 'upstream'); upstream = git('rev-parse', 'HEAD')
            git('update-ref', 'refs/remotes/origin/main', upstream)
            git('checkout', branch); git('merge', '--no-edit', 'upstream')
            with patch.object(u, 'ROOT', str(root)), patch.object(u, 'MANIFEST', str(root/'MANIFEST.json')), redirect_stdout(io.StringIO()):
                files = u.changed_files()
                self.assertEqual(files, ['nexclash/shared.py'])
                source, originals = u.contribution_base(files)
                self.assertEqual(source['commit'], upstream)
                self.assertEqual(originals, {'nexclash/shared.py': hashlib.md5(b'original').hexdigest()})
                for old in [start, before_refresh]:
                    with self.assertRaisesRegex(SystemExit, 'current merge base'):
                        u.changed_files(old)
                self.assertEqual(u.resolve_git_base('HEAD'), git('rev-parse', 'HEAD'))
                git('update-ref', '-d', 'refs/remotes/origin/main')
                self.assertEqual(u.resolve_git_base(start), start)

    def test_new_configuration_dependency_and_skill_files_roundtrip(self):
        importer = load('tools/merge_contribution.py')
        with repository() as (root, git):
            receiving = root.parent/'receiving'; git('worktree', 'add', '--detach', receiving, 'HEAD')
            files = {'requirements.txt': 'dependency', 'CONTRIBUTING.md': 'guide',
                     '.github/workflows/checks.yml': 'name: checks', '.claude/skills/new/SKILL.md': 'skill',
                     'VERSION': '1.0.0', 'LICENSE': 'license', 'THIRD-PARTY-NOTICES': 'notices',
                     '.gitignore': 'contrib_reports/\n.venv/\n'}
            for name, text in files.items():
                path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
            output = root.parent/'contribution.zip'
            with patch.object(u, 'ROOT', str(root)), patch.object(u, 'MANIFEST', str(root/'MANIFEST.json')), \
                 patch.object(u, 'CONTRIB', str(root/'none.json')), redirect_stdout(io.StringIO()):
                self.assertEqual(u.cmd_contribute(args(output)), 0)
            with zipfile.ZipFile(output) as z:
                self.assertEqual(set(json.loads(z.read('CONTRIBUTION.json'))['files']), set(files))
            with patch.object(importer, 'ROOT', str(receiving)), patch('sys.argv', ['merge', str(output)]), redirect_stdout(io.StringIO()):
                importer.main()
            for name, text in files.items():
                self.assertEqual((receiving/name).read_text(), text)

    def test_unsupported_changes_block_export_until_explicitly_excluded(self):
        for oversized in [False, True]:
            with self.subTest(oversized=oversized), repository() as (root, git):
                (root/'nexclash/shared.py').write_bytes(b'contributor')
                blocked = 'requirements.txt' if oversized else 'scratch.txt'
                (root/blocked).write_text('x' * (u.MAX_FILE+1) if oversized else 'unrelated note')
                output = root.parent/'contribution.zip'; output.write_bytes(b'previous archive')
                with patch.object(u, 'ROOT', str(root)), patch.object(u, 'MANIFEST', str(root/'MANIFEST.json')), \
                     patch.object(u, 'CONTRIB', str(root/'none.json')), redirect_stdout(io.StringIO()):
                    self.assertEqual(u.cmd_contribute(args(output)), 1)
                    self.assertEqual(output.read_bytes(), b'previous archive')
                    a = args(output); a.exclude = [blocked]
                    self.assertEqual(u.cmd_contribute(a), 0)
                    with zipfile.ZipFile(output) as z:
                        meta = json.loads(z.read('CONTRIBUTION.json'))
                    self.assertEqual(meta['excluded'], [blocked])
                    self.assertEqual(set(meta['files']), {'nexclash/shared.py'})
                    a.exclude = ['typo.txt']
                    with self.assertRaisesRegex(SystemExit, 'does not name changed files'):
                        u.cmd_contribute(a)

    def test_unsupported_toolkit_artwork_cannot_be_silently_dropped(self):
        with repository() as (root, git):
            (root/'nexclash/shared.py').write_bytes(b'contributor')
            asset = root/'assets/new.png'; asset.parent.mkdir(); asset.write_bytes(b'owner artwork')
            output = root.parent/'contribution.zip'
            with patch.object(u, 'ROOT', str(root)), patch.object(u, 'MANIFEST', str(root/'MANIFEST.json')), redirect_stdout(io.StringIO()):
                self.assertEqual(u.cmd_contribute(args(output)), 1)
            self.assertFalse(output.exists())

    def test_package_walk_prunes_noise_before_hashing_or_descending(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/'README.md').write_bytes(b'original')
            tracked = root/'docs/tracked.log'; tracked.parent.mkdir(); tracked.write_bytes(b'changed tracked log')
            (root/'MANIFEST.json').write_text(json.dumps({'files': {
                'README.md': hashlib.md5(b'original').hexdigest(), 'docs/tracked.log': hashlib.md5(b'original log').hexdigest()}}))
            path = root/'nexclash/new.py'; path.parent.mkdir(); path.write_text('new source')
            noise(root)
            original_walk, original_md5 = u.os.walk, u.md5
            visited, hashed = [], []
            def walk(*a, **k):
                for directory, dirs, fs in original_walk(*a, **k):
                    visited.append(Path(directory).relative_to(root).as_posix())
                    yield directory, dirs, fs
            def md5(path):
                hashed.append(Path(path).relative_to(root).as_posix())
                return original_md5(path)
            with patch.object(u, 'ROOT', d), patch.object(u, 'MANIFEST', str(root/'MANIFEST.json')), \
                 patch.object(u.os, 'walk', side_effect=walk), patch.object(u, 'md5', side_effect=md5):
                self.assertEqual(u.changed_files(), ['docs/tracked.log', 'nexclash/new.py'])
                with self.assertRaisesRegex(SystemExit, 'only to Git'):
                    u.changed_files('HEAD')
            self.assertEqual(set(hashed), {'README.md', 'docs/tracked.log'})
            self.assertFalse(any('.venv' in p or '_session' in p or '_survey' in p for p in visited))
            self.assertNotIn('node_modules', visited)

    def test_git_discovery_prunes_noise_but_keeps_modified_tracked_files(self):
        with repository() as (root, git):
            tracked = root/'docs/tracked.log'; tracked.parent.mkdir(); tracked.write_text('tracked log')
            git('add', '-f', tracked); git('commit', '-m', 'tracked log')
            git('update-ref', 'refs/remotes/origin/main', 'HEAD')
            tracked.write_text('updated log'); (root/'nexclash/shared.py').write_text('contributor')
            noise(root)  # The fixture's .gitignore intentionally lacks all the new ignore rules.
            with patch.object(u, 'ROOT', str(root)), patch.object(u, 'MANIFEST', str(root/'MANIFEST.json')), redirect_stdout(io.StringIO()):
                self.assertEqual(u.changed_files(), ['docs/tracked.log', 'nexclash/shared.py'])

    def test_player_inputs_are_summarised_not_hashed_or_exported(self):
        with repository() as (root, git):
            (root/'nexclash/shared.py').write_bytes(b'contributor')
            (root/'Game.z80').write_bytes(b'player input')
            output = root.parent/'contribution.zip'; original = u.md5
            def md5(path):
                self.assertNotEqual(Path(path).name, 'Game.z80')
                return original(path)
            with patch.object(u, 'ROOT', str(root)), patch.object(u, 'MANIFEST', str(root/'MANIFEST.json')), \
                 patch.object(u, 'CONTRIB', str(root/'none.json')), patch.object(u, 'md5', side_effect=md5), \
                 redirect_stdout(io.StringIO()) as text:
                self.assertEqual(u.cmd_contribute(args(output)), 0)
            self.assertIn('Excluded 1 game-data/binary', text.getvalue())
            with zipfile.ZipFile(output) as z:
                self.assertNotIn('files/Game.z80', z.namelist())


if __name__ == '__main__':
    unittest.main(verbosity=2)
