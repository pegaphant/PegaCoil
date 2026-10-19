"""Selbst-Aktualisierung mit einem nachgebauten GitHub (lokales origin-Repository)."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pegacoil import update  # noqa: E402


def git(cwd, *args):
    subprocess.run(['git', '-C', cwd, '-c', 'user.name=t', '-c', 'user.email=t@t'] + list(args),
                   check=True, capture_output=True)


@unittest.skipUnless(shutil.which('git'), 'git fehlt')
class Update(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.origin = os.path.join(self.tmp, 'origin.git')
        self.dev = os.path.join(self.tmp, 'dev')
        self.addin = os.path.join(self.tmp, 'addin')
        git(self.tmp, 'init', '--bare', '-b', 'main', self.origin)
        git(self.tmp, 'clone', self.origin, self.dev)
        self._commit('a.py', 'v1')
        git(self.tmp, 'clone', self.origin, self.addin)
        self.root, update.ROOT = update.ROOT, self.addin

    def tearDown(self):
        update.ROOT = self.root
        update._state.update(done=False, pulled=False, files=[], behind=0, ahead=0, dirty=False, error=None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _commit(self, name, text):
        with open(os.path.join(self.dev, name), 'w') as f:
            f.write(text)
        git(self.dev, 'add', name)
        git(self.dev, 'commit', '-m', text)
        git(self.dev, 'push', '-q', 'origin', 'HEAD:main')

    def _read(self, name):
        with open(os.path.join(self.addin, name)) as f:
            return f.read()

    def test_pulls_new_version(self):
        self._commit('a.py', 'v2')
        update.check_and_pull()
        self.assertEqual(self._read('a.py'), 'v2')
        self.assertEqual(update.take_pulled(), ['a.py'])
        self.assertEqual(update.take_pulled(), [])  # nur einmal melden
        self.assertIn('aktuell', update.status_text())

    def test_up_to_date(self):
        update.check_and_pull()
        self.assertEqual(update.take_pulled(), [])
        self.assertIn('aktuell', update.status_text())

    def test_local_changes_are_never_overwritten(self):
        self._commit('a.py', 'v2')
        with open(os.path.join(self.addin, 'a.py'), 'w') as f:
            f.write('lokal')
        update.check_and_pull()
        self.assertEqual(self._read('a.py'), 'lokal')
        self.assertEqual(update.take_pulled(), [])
        self.assertIn('nicht automatisch', update.status_text())

    def test_offline(self):
        git(self.addin, 'remote', 'set-url', 'origin', os.path.join(self.tmp, 'gibtsnicht.git'))
        update.check_and_pull()
        self.assertIn('nicht erreichbar', update.status_text())


if __name__ == '__main__':
    unittest.main()
